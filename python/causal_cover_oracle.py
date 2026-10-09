# SPDX-License-Identifier: GPL-3.0-or-later
"""Finite boundary-coordinate rectangle-cover oracle for a pinned grammar.

All contained covers and both axes are in scope. Existing impossible relation
domains are pruned by the pinned diagnostic CSP, never by aesthetic ranking.
Incomplete inputs do not establish nonrepresentability.
"""
import argparse
from collections import Counter
import importlib.util
from itertools import islice
import json
from pathlib import Path
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root',type=Path,required=True)
    parser.add_argument('--source-sha',required=True)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-work',type=int,default=100000)
    parser.add_argument('--max-assignments',type=int,default=100000)
    args=parser.parse_args()
    sys.path.insert(0,str(args.code_root/'addon'))
    spec=importlib.util.spec_from_file_location('pinned_cover_probe',args.code_root/'python/probe_region_covers.py')
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    from roof_generator.core.solve import problem,solve
    from roof_generator.core.errors import UnsupportedRoofError
    records=json.loads(args.inputs.read_bytes())['inputs']
    rows=[]
    for index,record in enumerate(records):
        fp=probe.analyze(record['footprint'])
        # One rectangle per occupied coordinate box bounds every possible
        # member count; this oracle has no hidden six-member truncation.
        maximum=(len({p[0] for p in fp.vertices})-1)*(len({p[1] for p in fp.vertices})-1)
        covers,state=probe.covers(fp,maximum,args.max_work)
        rejections=Counter();axes=0;graphs=0;meshes=0;empty=0;implicit_axes=0
        for rings in covers:
            proposal=probe.propose_regions(fp,rings,source='coordinate_cover_oracle')
            architecture=probe.interpret_regions(proposal)
            implicit_axes+=2**len(architecture.members)
            any_axis=False
            for assignment in probe.assignments(architecture):
                any_axis=True;axes+=1
                if axes>args.max_assignments:
                    state.update(complete=False,reason='oracle axis/end work budget exhausted');break
                resolved=probe.resolve(architecture,assignment)
                try:
                    choices=tuple(islice(probe.roof_configurations(resolved,probe.symmetry_clusters(resolved.analysis())),args.max_assignments-axes+2))
                    if not choices:
                        rejections['ends: no global configuration']+=1
                except UnsupportedRoofError as exc:
                    rejections['ends: '+str(exc)]+=1;continue
                for choice_index,choice in enumerate(choices):
                    if choice_index:
                        axes+=1
                        if axes>args.max_assignments:
                            state.update(complete=False,reason='oracle axis/end work budget exhausted');break
                    stage='architecture'
                    try:
                        authority=resolved.with_ends(choice)
                        stage='composition';composition=probe.compose(authority);graphs+=1
                        stage='geometry_problem';geometry=problem(composition.graph)
                        stage='embedding';mesh=solve(composition.graph,geometry)
                        if mesh.graph is not composition.graph:
                            raise RuntimeError('solver changed oracle graph')
                        meshes+=1
                    except UnsupportedRoofError as exc:
                        rejections[stage+': '+str(exc)]+=1
                if not state['complete']:
                    break
            if not any_axis:
                empty+=1
            if not state['complete']:
                break
        row={'name':record['name'],'category':record['category'],'vertices':len(record['footprint']),
             'search':state,'covers_without_supported_axes':empty,
             'all_axis_combinations_in_cover_domain':implicit_axes,'evaluated_axis_end_choices':axes,
             'graphs':graphs,'embeddings':meshes,'selectable':state['complete'] and meshes>0,
             'rejections':dict(rejections)}
        rows.append(row)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        report={'source_sha':args.source_sha,'scope':__doc__,'inputs':len(records),
                'finished_inputs':len(rows),'complete':sum(r['search']['complete'] for r in rows),
                'selectable':sum(r['selectable'] for r in rows),'rows':rows}
        args.output.write_bytes((json.dumps(report,indent=2)+'\n').encode())
        print(index+1,len(records),record['name'],state['complete'],graphs,meshes,flush=True)


if __name__=='__main__':main()
