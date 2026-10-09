# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded region-guided global ends; complete intent, never partial matching.

Minimum and receiver proposals are peers, not fallback backends. Both axes are
an explicit diagnostic domain; long-axis results are recorded separately. No
ranking or seed selection. Missing cap support is an intent-domain gap, not a
proof that the intended roof is impossible. Each input has a hard wall budget.
The maximal mode gives each region/axis model componentwise gable preference;
the exhaustive mode retains every explicit mixed hip/gable configuration.
"""
import argparse
from collections import Counter
import gzip
import hashlib
from itertools import combinations
import math
import json
from pathlib import Path
import subprocess
import sys
import time


SOURCES = ('roof_intent.py', 'probe_roof_intent.py', 'whole_polygon_roofs.py')


def inspect(record, max_assignments, mode, axis_policy):
    from py_straight_skeleton import compute_skeleton
    from roof_generator.core.footprint import analyze, EPS
    from roof_generator.core.cells import decompose
    from roof_generator.core.member_layout import member_layout
    from roof_generator.core.roof_regions import minimum_regions
    from roof_generator.core.receiver_regions import receiver_regions
    from roof_generator.core import graph as graph_api
    from roof_generator.core.provenance import BoundaryPoint
    from roof_generator.core.errors import UnsupportedRoofError
    from roof_generator.core.solve import problem, solve
    from python.roof_intent import (RoofIntent, topology, cap_domain,
                                   gable_configurations, CapConfiguration)
    started = time.perf_counter()
    row = dict(name=record['name'], category=record.get('category','user_images'),
               embedded=False, long_axis_embedded=False, stage='skeleton',
               search_complete=False, domain_checks=0, end_configurations=0,
               pure_gable_embedded=False, rejections={}, families=[], mode=mode,axis_policy=axis_policy)
    fp = analyze(record['footprint'])
    try:
        skeleton = compute_skeleton(
            exterior=[(x*fp.frame.scale,y*fp.frame.scale) for x,y in fp.vertices], holes=[])
    except Exception as exc:
        return dict(row, stage='dependency', error=type(exc).__name__+': '+str(exc),
                    elapsed_seconds=time.perf_counter()-started)
    n = len(fp.vertices)
    available = tuple(face[0] for face in skeleton.get_faces() if len(face)==4 and face[2]>=n)
    row['available_caps'] = available
    if mode=='maximal':
        available,conflicts,blocked=cap_domain(fp,skeleton)
        row.update(cap_conflicts=conflicts,blocked_caps=blocked)
    row['stage'] = 'region_search'
    try:
        minimum = minimum_regions(decompose(fp))
        receiver = receiver_regions(fp)
    except Exception as exc:
        return dict(row, error=type(exc).__name__+': '+str(exc),
                    elapsed_seconds=time.perf_counter()-started)
    families = [('minimum', (minimum,), True, None),
                ('receiver', receiver.proposals if receiver.complete else (),
                 receiver.complete, receiver.reason)]
    # A cap configuration is global: region origins cannot multiply identical
    # graphs. Keep all declarations, but construct each explicit cap set once.
    choices = {}; failures = Counter(); incomplete = False
    subsets = (tuple(tuple(c) for count in range(1,len(available)+1)
                     for c in combinations(available,count)) if len(available)<=12 else ())
    if mode=='exhaustive' and len(available)>12: incomplete = True
    for source, candidates, complete, reason in families:
        summary = dict(source=source, region_proposals=len(candidates), complete=complete,
                       pure_axis_assignments=0, pure_represented_axes=0,
                       mixed_configurations=0, pure_embedded_configurations=0,
                       embedded_configurations=0, long_axis_embedded_configurations=0,
                       reason=reason)
        if not complete: incomplete = True
        for candidate in candidates:
            layout = member_layout(candidate)
            long_axes = []
            for region in candidate.regions:
                sizes = tuple(max(p[k] for p in region.boundary)-min(p[k] for p in region.boundary)
                              for k in (0,1))
                long_axes.append({0,1} if abs(sizes[0]-sizes[1])<=4*EPS
                                 else {0 if sizes[0]>sizes[1] else 1})
            declared_axes=tuple(tuple(sorted(a)) for a in long_axes) if axis_policy=='long' else ((0,1),)*len(candidate.regions)
            summary['pure_axis_assignments']+=math.prod(map(len,declared_axes))
            remaining_work=max_assignments-row['domain_checks']
            if remaining_work<=0:
                incomplete=True;summary['complete']=False
                summary['reason']='intent domain work budget exhausted';break
            if mode=='maximal':
                pool=gable_configurations(layout,available,conflicts,blocked,
                                          axes=declared_axes,max_work=remaining_work)
                row['domain_checks']+=pool.work
                if not pool.complete:
                    incomplete = True; summary['complete'] = False
                    summary['reason']=pool.reason;break
                configurations=pool.configurations
            else:
                configurations=[]
                for selected in subsets:
                    row['domain_checks']+=1
                    if row['domain_checks']>max_assignments:
                        incomplete=True;summary['complete']=False
                        summary['reason']='intent domain work budget exhausted';break
                    domains=tuple(tuple(v for v in a if v in b) for a,b in zip(
                        RoofIntent.axis_domains(layout,selected),declared_axes))
                    if all(domains):configurations.append(CapConfiguration(selected,domains))
                    else:failures['intent_domain']+=1
            for configuration in configurations:
                selected,domains=configuration.selected,configuration.axis_domains
                pure_domains = tuple(tuple(v for v in a if v in b) for a,b in zip(
                    RoofIntent.axis_domains(layout,selected,'gable'),domains))
                pure = all(pure_domains)
                if pure:
                    summary['pure_represented_axes'] += math.prod(map(len,pure_domains))
                is_long = all(set(domain)&long for domain,long in zip(domains,long_axes))
                summary['mixed_configurations'] += 1; row['end_configurations'] += 1
                # Free axes are a factorized alternative set, not a priority.
                # One representative carries the same exterior declaration
                # into the global backend; interior ridge intent is not tested.
                axes = tuple(domain[0] for domain in domains)
                resolved = RoofIntent.from_caps(layout,axes,selected)
                if selected not in choices:
                    result = dict(selected_caps=selected, embedded=False, stage='topology',
                                  origins=[])
                    try:
                        roof, decisions = topology(resolved, fp, skeleton, graph_api,
                                                   BoundaryPoint, UnsupportedRoofError)
                        result['stage'] = 'geometry_problem'; geometry = problem(roof)
                        result['stage'] = 'embedding'; mesh = solve(roof,geometry)
                        if mesh.graph is not roof: raise RuntimeError('intent solve changed topology')
                        result.update(stage='mesh', embedded=True)
                        if not row['embedded']:
                            row.update(graph=roof.inspect(), decisions=decisions,
                                       vertices=mesh.vertices, faces=mesh.faces,
                                       witness_scope='first visualization witness only; not seed selection')
                    except Exception as exc:
                        result['error'] = type(exc).__name__+': '+str(exc)
                    choices[selected] = result
                result = choices[selected]
                result['origins'].append(dict(source=source,region_id=candidate.id,
                    axis_domains=domains,pure_gable_axis_domains=pure_domains,
                    long_axis_compatible=is_long))
                if result['embedded']:
                    row['embedded'] = True
                    row['long_axis_embedded'] |= is_long
                    row['pure_gable_embedded'] |= pure
                    summary['embedded_configurations'] += 1
                    summary['pure_embedded_configurations'] += int(pure)
                    summary['long_axis_embedded_configurations'] += int(is_long)
                else:
                    failures[result['stage']] += 1
            if not summary['complete']: break
        if summary['complete'] and (mode=='maximal' or len(available)<=12):
            summary['unrepresented_pure_axes'] = summary['pure_axis_assignments']-summary['pure_represented_axes']
        row['families'].append(summary)
    row.update(search_complete=not incomplete, choices=list(choices.values()),
               rejections=dict(failures),
               elapsed_seconds=time.perf_counter()-started)
    row['stage'] = ('search_incomplete' if incomplete else 'mesh' if row['embedded']
                    else 'topology' if choices else 'intent_domain')
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--deps', type=Path, required=True)
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--category')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--seconds', type=float, default=15)
    parser.add_argument('--max-assignments', type=int, default=65536)
    parser.add_argument('--mode',choices=('maximal','exhaustive'),default='maximal')
    parser.add_argument('--axes',choices=('long','all'),default='long')
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.seconds<=0 or args.max_assignments<1: raise ValueError('positive budgets required')
    root = args.code_root.resolve()
    sys.path.insert(0,str(root)); sys.path.insert(0,str(root/'addon')); sys.path.insert(0,str(args.deps))
    if args.worker:
        print(json.dumps(inspect(json.loads(sys.stdin.read()),args.max_assignments,args.mode,args.axes)))
        return
    if args.inputs is None or args.output is None: parser.error('--inputs and --output required')
    payload = args.inputs.read_bytes()
    if args.inputs.suffix=='.gz': payload=gzip.decompress(payload)
    data = json.loads(payload)
    records = ([dict(r,category=args.category) for r in data['corpora'][args.category]]
               if args.category else data['inputs'])
    hashes = {name:hashlib.sha256(Path(__file__).with_name(name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
              for name in SOURCES}
    core = {p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
            for p in sorted((root/'addon/roof_generator/core').glob('*.py'))}
    rows = []; args.output.parent.mkdir(parents=True,exist_ok=True)
    command = [sys.executable,str(Path(__file__).resolve()),'--worker',
               '--code-root',str(root),'--deps',str(args.deps.resolve()),
               '--max-assignments',str(args.max_assignments),'--mode',args.mode,'--axes',args.axes]
    for record in records:
        try:
            run = subprocess.run(command,input=json.dumps(record),capture_output=True,
                                 text=True,timeout=args.seconds)
            if run.returncode: raise RuntimeError(run.stderr[-2000:])
            row = json.loads(run.stdout)
        except subprocess.TimeoutExpired:
            row = dict(name=record['name'],category=record.get('category','user_images'),
                       embedded=False,long_axis_embedded=False,stage='search_incomplete',
                       search_complete=False,error='wall budget exhausted; no negative feasibility claim')
        rows.append(row)
        report = dict(scope=__doc__, inputs_sha256=hashlib.sha256(payload).hexdigest(),
                      diagnostic_source_files_sha256=hashes,core_source_files_sha256=core,
                      budgets=dict(seconds=args.seconds,axis_assignments=args.max_assignments),
                      mode=args.mode,axis_policy=args.axes,
                      requested_inputs=len(records),finished_inputs=len(rows),
                      embedded_inputs=sum(r['embedded'] for r in rows),
                      long_axis_embedded_inputs=sum(r['long_axis_embedded'] for r in rows),
                      pure_gable_embedded_inputs=sum(r.get('pure_gable_embedded',False) for r in rows),
                      complete_inputs=sum(r['search_complete'] for r in rows),
                      stages=dict(Counter(r['stage'] for r in rows)),rows=rows)
        args.output.write_bytes((json.dumps(report,indent=2)+'\n').encode())
        if len(rows)%10==0 or len(rows)==len(records):
            print(len(rows),len(records),report['embedded_inputs'],report['stages'],flush=True)


if __name__ == '__main__': main()
