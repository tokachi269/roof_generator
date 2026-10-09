# SPDX-License-Identifier: GPL-3.0-or-later
"""Existence comparison for declared roof extension composition.

The first verified witness certifies constructibility, not an architectural
recommendation or seed-selectable complete candidate pool. Exhausted budgets
are censored. No old grammar filtering, end CSP or junction templates are used.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

from hybrid_roofs import Architecture, HybridError, assignments, bounds, coordinates, topology


def inspect(record, api, *, max_work=65536, max_candidates=4096, max_assignments=4096):
    analyze,recursive_regions,graph_api,BoundaryPoint,problem,solve=api
    row={'name':record['name'],'category':record.get('category','user_images'),
         'embedded':False,'stage':'region_search','search_complete':False,
         'axis_assignments':0,'rejections':{},'elapsed_seconds':None}
    started=time.perf_counter();failures=Counter()
    fp=analyze(record['footprint'])
    outline,maps=coordinates(fp,record['footprint'])
    search=recursive_regions(fp,max_work=max_work,max_candidates=max_candidates)
    row.update(region_proposals=len(search.proposals),region_search_complete=search.complete,
               region_search_work=search.work)
    if not search.complete:
        row.update(stage='search_incomplete',error=search.reason,elapsed_seconds=time.perf_counter()-started)
        return row
    row['stage']='architecture';witness=False;incomplete=False
    graph_count=0
    for candidate in search.proposals:
        boxes=bounds(candidate,maps);tested=0
        for axes in assignments(boxes):
            if row['axis_assignments']>=max_assignments:
                incomplete=True;break
            tested+=1;row['axis_assignments']+=1
            stage='composition'
            try:
                architecture=Architecture.declare(boxes,axes)
                graph,decisions=topology(fp,architecture,graph_api,BoundaryPoint,outline)
                graph_count+=1
                stage='geometry_problem';geometry=problem(graph)
                stage='embedding';mesh=solve(graph,geometry)
                if mesh.graph is not graph:raise RuntimeError('hybrid solver changed topology')
                row.update(embedded=True,stage='mesh',decisions=decisions,proposal=candidate.inspect(),
                           graph=graph.inspect(),vertices=mesh.vertices,faces=mesh.faces)
                witness=True;break
            except Exception as exc:
                # Concrete construction errors remain diagnostic evidence.
                # They never activate a different generation backend.
                failures[stage+': '+type(exc).__name__+': '+str(exc)]+=1
        if not tested:failures['architecture: no declared contact-compatible axis assignment']+=1
        if witness or incomplete:break
    row.update(graphs=graph_count,rejections=dict(failures),
               search_complete=not witness and not incomplete,
               existence_certified=witness,elapsed_seconds=time.perf_counter()-started)
    if incomplete:row.update(stage='search_incomplete',error='hybrid axis/composition work budget exhausted')
    elif not witness:
        row['stage']='embedding' if graph_count else 'composition' if row['axis_assignments'] else 'architecture'
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root',type=Path,required=True)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--category')
    parser.add_argument('--case',action='append')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-work',type=int,default=65536)
    parser.add_argument('--max-candidates',type=int,default=4096)
    parser.add_argument('--max-assignments',type=int,default=4096)
    args=parser.parse_args()
    sys.path.insert(0,str(args.code_root/'addon'))
    from roof_generator.core.footprint import analyze
    from roof_generator.core.recursive_regions import recursive_regions
    from roof_generator.core import graph as graph_api
    from roof_generator.core.provenance import BoundaryPoint
    from roof_generator.core.solve import problem,solve
    payload=args.inputs.read_bytes()
    if args.inputs.suffix=='.gz':payload=gzip.decompress(payload)
    data=json.loads(payload)
    records=[dict(r,category=args.category) for r in data['corpora'][args.category]] if args.category else data['inputs']
    if args.case:records=[r for r in records if r['name'] in args.case]
    hashes={p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
            for p in sorted((args.code_root/'addon/roof_generator/core').glob('*.py'))}
    diagnostics={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
                 for name in ('hybrid_roofs.py','probe_hybrid_roofs.py')}
    rows=[];api=(analyze,recursive_regions,graph_api,BoundaryPoint,problem,solve)
    for index,record in enumerate(records):
        row=inspect(record,api,max_work=args.max_work,max_candidates=args.max_candidates,max_assignments=args.max_assignments)
        rows.append(row)
        report={'scope':__doc__,'inputs_sha256':hashlib.sha256(payload).hexdigest(),
                'core_source_files_sha256':hashes,'diagnostic_source_files_sha256':diagnostics,
                'requested_inputs':len(records),'finished_inputs':len(rows),
                'embedded_inputs':sum(r['embedded'] for r in rows),
                'stages':dict(Counter(r['stage'] for r in rows)),
                'search_budgets':{'region_work':args.max_work,'region_candidates':args.max_candidates,'axis_assignments':args.max_assignments},
                'rows':rows}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_bytes((json.dumps(report,indent=2)+'\n').encode())
        print(index+1,len(records),row['name'],row['stage'],round(row['elapsed_seconds'],3),flush=True)


if __name__=='__main__':main()
