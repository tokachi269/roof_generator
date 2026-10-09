# SPDX-License-Identifier: GPL-3.0-or-later
"""Construction test of explicit alternative ends at shared cap events.

For the frozen 84 failures, every conflicting pair gets two explicit intents:
one gable and one retained hip. All nonconflicting original gable intentions
stay fixed. Every product is tested, with no geometry-dependent selection,
seed selection, fallback or architectural recommendation. Region-guided end
preferences and a genuine global delayed wavefront remain unimplemented.
"""
import argparse
from collections import Counter
import gzip
import hashlib
from itertools import product
import json
from pathlib import Path
import sys
import time

from whole_polygon_roofs import topology


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root',type=Path,required=True)
    parser.add_argument('--deps',type=Path,required=True)
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--frontier',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    sys.path.insert(0,str(args.code_root/'addon'));sys.path.insert(0,str(args.deps))
    from py_straight_skeleton import compute_skeleton
    from roof_generator.core.footprint import analyze
    from roof_generator.core import graph as graph_api
    from roof_generator.core.provenance import BoundaryPoint
    from roof_generator.core.errors import UnsupportedRoofError
    from roof_generator.core.solve import problem,solve
    payload=gzip.decompress(args.corpus.read_bytes())
    records={r['name']:r for r in json.loads(payload)['corpora']['orthogonal_grid_stress']}
    frontier=json.loads(args.frontier.read_bytes())
    rows=[]
    for case in frontier['rows']:
        started=time.perf_counter();fp=analyze(records[case['name']]['footprint'])
        skeleton=compute_skeleton(exterior=[(x*fp.frame.scale,y*fp.frame.scale) for x,y in fp.vertices],holes=[])
        groups=[tuple(event['cap_edges']) for event in case['shared_events']]
        if any(len(group)!=2 for group in groups):raise RuntimeError('frozen pair experiment domain changed')
        fixed={edge for edge,node in case['caps']}-{edge for group in groups for edge in group}
        candidates=[]
        for selected in product(*groups):
            choice=tuple(sorted(fixed|set(selected)))
            row={'name':case['name'],'category':'orthogonal_grid_stress','selected_caps':choice,
                 'retained_hip_caps':sorted({edge for edge,node in case['caps']}-set(choice)),
                 'embedded':False,'stage':'topology'}
            try:
                graph,decisions=topology(fp,lambda **kwargs:skeleton,graph_api,BoundaryPoint,UnsupportedRoofError,selected_caps=choice)
                row.update(graph=graph.inspect(),decisions=decisions,stage='geometry_problem')
                geometry=problem(graph);row['stage']='embedding';mesh=solve(graph,geometry)
                if mesh.graph is not graph:raise RuntimeError('cap choice solver changed topology')
                row.update(stage='mesh',embedded=True,vertices=mesh.vertices,faces=mesh.faces)
            except Exception as exc:row['error']=type(exc).__name__+': '+str(exc)
            candidates.append(row)
        rows.append({'name':case['name'],'intents':len(candidates),'embedded_intents':sum(r['embedded'] for r in candidates),
                     'elapsed_seconds':time.perf_counter()-started,'candidates':candidates})
        report={'scope':__doc__,'corpus_sha256':hashlib.sha256(payload).hexdigest(),
                'frontier_sha256':hashlib.sha256(args.frontier.read_bytes()).hexdigest(),
                'source_files_sha256':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
                                      for name in ('whole_polygon_roofs.py','probe_cap_choices.py')},
                'core_source_files_sha256':{p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
                                            for p in sorted((args.code_root/'addon/roof_generator/core').glob('*.py'))},
                'requested_inputs':len(frontier['rows']),'finished_inputs':len(rows),
                'inputs_with_embedded_intent':sum(r['embedded_intents']>0 for r in rows),
                'candidate_stages':dict(Counter(c['stage'] for r in rows for c in r['candidates'])),'rows':rows}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_bytes((json.dumps(report,indent=2)+'\n').encode())
        if len(rows)%10==0 or len(rows)==len(frontier['rows']):
            print(len(rows),len(frontier['rows']),report['inputs_with_embedded_intent'],report['candidate_stages'],flush=True)


if __name__=='__main__':main()
