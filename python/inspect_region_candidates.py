# SPDX-License-Identifier: GPL-3.0-or-later
"""Four screenshot proposal sources through the polygon contract, not RoofGraph."""
import argparse
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addon'))
from roof_generator.core.footprint import analyze
from roof_generator.core.partition_candidates import candidates
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.core.roof_regions import propose_regions, minimum_regions, parallel_recommendation
from shapely.geometry import Polygon
from shapely.ops import unary_union


def inspect(report):
    cases = []
    for case in report['cases']:
        if not case['input']['name'].startswith('user_image_'):
            continue
        fp = analyze(case['input']['footprint'])
        search = candidates(fp)
        if not search.complete:
            raise UnsupportedRoofError('source minimum search incomplete')
        decomposition = search.candidates[0]
        records = []
        def record(outlines,source):
            try:
                candidate = propose_regions(fp,outlines,source=source,provenance=decomposition)
                # Explicit long-axis rectangle-model probe only, not a resolved
                # architectural interpretation or a production model assignment.
                bounds = [Polygon(r.boundary).bounds for r in candidate.regions]
                axes = tuple(int(b[3]-b[1]>b[2]-b[0]) for b in bounds)
                records.append(candidate.inspect()|{'long_axis_probe':axes,
                               'recommendation_probe':asdict(parallel_recommendation(candidate,axes))})
            except UnsupportedRoofError as exc:
                records.append({'source':source,'rejection':str(exc),'validation_stage':'2D support'})
        for i,d in enumerate(search.candidates):
            proposal = minimum_regions(d)
            record([tuple(fp.frame.world_xy(p) for p in r.boundary) for r in proposal.regions],f'minimum:{i}')
        atoms = [Polygon(a['exterior'],a['holes']) for a in case['atoms']]
        for index,configuration in enumerate(case['priority_exhaustion']['configurations']):
            outlines = []
            for region in configuration['regions']:
                union = unary_union([atoms[i] for i in region['atoms']])
                if union.geom_type!='Polygon' or union.interiors:
                    # Do not split components or fill holes under another owner.
                    outlines = None
                    break
                outlines.append(tuple(fp.frame.world_xy(p) for p in list(union.exterior.coords)[:-1]))
            source = f'Laycock_order_probe:{index}'
            if outlines is None:
                records.append({'source':source,'rejection':'collection is disconnected or has holes',
                                'validation_stage':'2D support'})
            else:
                record(outlines,source)
        accepted = [r for r in records if 'id' in r]
        cases.append({'name':case['input']['name'],'input':case['input'],
                      'frame':asdict(fp.frame),'provenance_partition':decomposition.inspect(),'records':records,
                      'accepted_2D_sources':len(accepted),
                      'distinct_2D_candidates':len({r['id'] for r in accepted}),
                      'rejected_sources':len(records)-len(accepted),
                      'roof_valid_candidates':None,'roof_stage':'not constructed'})
    return {'scope':'Explicit proposals through production polygon contract; no runtime skeleton, model assignment or roof selection',
            'cases':cases}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=inspect(json.loads(gzip.decompress(args.report.read_bytes())))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    for case in result['cases']:
        print(case['name'],case['distinct_2D_candidates'],'distinct 2D candidates,',case['rejected_sources'],'rejected; no roof constructed')


if __name__=='__main__':
    main()
