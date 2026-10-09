# SPDX-License-Identifier: GPL-3.0-or-later
"""Region-guided global cap pool with soft axis preference and fixed embedding.

All proposal sources enter before construction. Candidate aliases do not
multiply probability mass. Every retained end configuration is checked; seed
selection is forbidden if any source or work budget remains incomplete. This
is a developer comparison, not the addon operator or a weighted wavefront.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


SOURCES=('roof_intent.py','roof_preference.py','probe_roof_preference.py','whole_polygon_roofs.py')


def inspect(record,max_work,seed):
    from py_straight_skeleton import compute_skeleton
    from roof_generator.core.footprint import analyze
    from roof_generator.core.cells import decompose
    from roof_generator.core.roof_regions import minimum_regions
    from roof_generator.core.receiver_regions import receiver_regions
    from roof_generator.core.member_layout import member_layout
    from roof_generator.core import graph as graph_api
    from roof_generator.core.provenance import BoundaryPoint
    from roof_generator.core.errors import UnsupportedRoofError
    from roof_generator.core.solve import problem,solve
    from roof_generator.core.seed import choose,derive,point_identity
    from python.roof_intent import RoofIntent,cap_domain,topology
    from python.roof_preference import recommend
    started=time.perf_counter();fp=analyze(record['footprint'])
    row=dict(name=record['name'],category=record.get('category','user_images'),
             embedded=False,search_complete=False,stage='dependency',families=[],choices=[],
             scope='exterior cap intent only; interior ridge intent and nonterminal gables unfulfilled')
    try:
        skeleton=compute_skeleton(exterior=[(x*fp.frame.scale,y*fp.frame.scale) for x,y in fp.vertices],holes=[])
        available,conflicts,blocked=cap_domain(fp,skeleton)
    except Exception as exc:
        return dict(row,error=type(exc).__name__+': '+str(exc),elapsed_seconds=time.perf_counter()-started)
    row.update(available_caps=available,cap_conflicts=conflicts,blocked_caps=blocked,stage='regions')
    minimum=minimum_regions(decompose(fp));receiver=receiver_regions(fp,max_work=max_work)
    families=(('minimum',(minimum,),True,None),
              ('receiver',receiver.proposals if receiver.complete else (),receiver.complete,receiver.reason))
    complete=True;work=0;results={};meshes={};failures=Counter()
    identity=point_identity(fp)
    outline=tuple(identity(p) for p in fp.vertices)
    for source,proposals,finished,reason in families:
        summary=dict(source=source,region_proposals=len(proposals),complete=finished,reason=reason,
                     end_configurations=0,work=0)
        if not finished:complete=False
        for proposal in proposals:
            remaining=max_work-work
            if remaining<=0:
                complete=False;summary.update(complete=False,reason='combined architecture work budget exhausted');break
            layout=member_layout(proposal)
            pool=recommend(layout,available,conflicts,blocked,max_work=remaining)
            work+=pool.work;summary['work']+=pool.work
            if not pool.complete:
                complete=False;summary.update(complete=False,reason=pool.reason);break
            for config in pool.configurations:
                selected=config.selected
                summary['end_configurations']+=1
                origin=dict(source=source,region_id=proposal.id,axis_domains=config.axis_domains)
                if selected not in results:
                    # IDs use declared exterior geometry, not external event
                    # numbering, Cell IDs, source order or solved coordinates.
                    ends=tuple(sorted(tuple(sorted((outline[e],outline[(e+1)%len(outline)]))) for e in selected))
                    code=derive(0,'global_roof',json.dumps((tuple(sorted(outline)),ends)))
                    result=dict(id=code,selected_caps=selected,embedded=False,stage='topology',origins=[])
                    try:
                        intent=RoofIntent.from_caps(layout,tuple(d[0] for d in config.axis_domains),selected)
                        graph,decisions=topology(intent,fp,skeleton,graph_api,BoundaryPoint,UnsupportedRoofError)
                        result['stage']='geometry_problem';geometry=problem(graph)
                        result['stage']='embedding';mesh=solve(graph,geometry)
                        if mesh.graph is not graph:raise RuntimeError('global end solve changed topology')
                        result.update(stage='mesh',embedded=True)
                        meshes[code]=(graph,decisions,mesh)
                    except Exception as exc:
                        result['error']=type(exc).__name__+': '+str(exc)
                    results[selected]=result
                result=results[selected];result['origins'].append(origin)
                if not result['embedded']:failures[result['stage']]+=1
        row['families'].append(summary)
    valid=tuple(r for r in results.values() if r['embedded'])
    row.update(choices=list(results.values()),embedded=complete and bool(valid),
               existence_certified=bool(valid),search_complete=complete,
               work=work,rejections=dict(failures),selectable_ids=[r['id'] for r in valid] if complete else [])
    if complete and valid:
        selected=choose(valid,seed,'roof_candidate',key=lambda r:r['id'])
        graph,decisions,mesh=meshes[selected['id']]
        row.update(stage='mesh',selected_id=selected['id'],graph=graph.inspect(),decisions=decisions,
                   vertices=mesh.vertices,faces=mesh.faces)
    elif not complete:
        row['stage']='search_incomplete'
    else:
        row['stage']='topology' if results else 'intent_domain'
    row['elapsed_seconds']=time.perf_counter()-started
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root',type=Path,required=True)
    parser.add_argument('--deps',type=Path,required=True)
    parser.add_argument('--inputs',type=Path)
    parser.add_argument('--category')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--max-work',type=int,default=65536)
    parser.add_argument('--seconds',type=float,default=15)
    parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--worker',action='store_true')
    args=parser.parse_args()
    if args.max_work<1 or args.seconds<=0:raise ValueError('positive search budgets required')
    root=args.code_root.resolve()
    sys.path.insert(0,str(root));sys.path.insert(0,str(root/'addon'));sys.path.insert(0,str(args.deps))
    if args.worker:
        print(json.dumps(inspect(json.loads(sys.stdin.read()),args.max_work,args.seed)));return
    if args.inputs is None or args.output is None:parser.error('--inputs and --output required')
    payload=args.inputs.read_bytes()
    if args.inputs.suffix=='.gz':payload=gzip.decompress(payload)
    data=json.loads(payload)
    records=([dict(r,category=args.category) for r in data['corpora'][args.category]] if args.category else data['inputs'])
    hashes={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for name in SOURCES}
    core={p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
          for p in sorted((root/'addon/roof_generator/core').glob('*.py'))}
    command=[sys.executable,str(Path(__file__).resolve()),'--worker','--code-root',str(root),
             '--deps',str(args.deps.resolve()),'--max-work',str(args.max_work),'--seed',str(args.seed)]
    args.output.parent.mkdir(parents=True,exist_ok=True);rows=[]
    for record in records:
        try:
            run=subprocess.run(command,input=json.dumps(record),text=True,capture_output=True,timeout=args.seconds)
            if run.returncode:raise RuntimeError(run.stderr[-2000:])
            row=json.loads(run.stdout)
        except subprocess.TimeoutExpired:
            row=dict(name=record['name'],category=record.get('category','user_images'),embedded=False,
                     stage='search_incomplete',search_complete=False,selectable_ids=[],
                     error='per-input wall budget exhausted; no negative feasibility claim')
        rows.append(row)
        report=dict(scope=__doc__,inputs_sha256=hashlib.sha256(payload).hexdigest(),
                    diagnostic_source_files_sha256=hashes,core_source_files_sha256=core,
                    budgets=dict(seconds=args.seconds,work=args.max_work),seed=args.seed,
                    requested_inputs=len(records),finished_inputs=len(rows),
                    selectable_inputs=sum(bool(r.get('selectable_ids')) for r in rows),
                    complete_inputs=sum(r['search_complete'] for r in rows),
                    stages=dict(Counter(r['stage'] for r in rows)),rows=rows)
        args.output.write_bytes((json.dumps(report,indent=2)+'\n').encode())
        if len(rows)%10==0 or len(rows)==len(records):
            print(len(rows),len(records),report['selectable_inputs'],report['stages'],flush=True)


if __name__=='__main__':main()
