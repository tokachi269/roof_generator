# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve explicit saved proposals; this is not a runtime proposal source."""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addon'))
from roof_generator.core.footprint import analyze
from roof_generator.core.roof_regions import propose_regions
from roof_generator.core.region_generation import region_candidates
from roof_generator.core.generation import GenerationSettings
from roof_generator.core.partition_candidates import candidates


def inspect(records):
    result=[]
    for case in records['cases']:
        fp=analyze(case['input']['footprint'])
        search=candidates(fp)
        if not search.complete:
            raise RuntimeError('diagnostic source provenance search is incomplete')
        source_partition=search.candidates[0]
        proposals=[]
        for record in case['records']:
            if 'id' not in record:continue
            outlines=[tuple(fp.frame.world_xy(p) for p in r['boundary']) for r in record['regions']]
            proposals.append(propose_regions(fp,outlines,source=record['source'],provenance=source_partition))
        pool=region_candidates(proposals,GenerationSettings(pitch=.5,max_axis_assignments=65536))
        row={'name':case['name'],'complete':pool.complete,'reason':pool.reason,
             'input':case['input'],'provenance_partition':source_partition.inspect(),
             'embedded_candidates':len(pool.valid),
             'ranking':pool.inspect_ranking(),
             'rejections':dict(Counter((r.stage+': '+r.reason) for r in pool.rejected)),
             'valid':[{'id':c.id,'axes':c.axes,'architecture':c.architecture.inspect(),
                       'ends':asdict(c.ends),'recommendation':asdict(c.recommendation),
                       'vertices':c.mesh.vertices,'faces':c.mesh.faces,
                       'connections':[asdict(r) for r in c.composition.connections],
                       'features':[asdict(f) for f in c.composition.features],
                       'graph':c.graph.inspect()} for c in pool.valid]}
        result.append(row)
        print(row['name'],row['embedded_candidates'],'embedded',row['complete'],flush=True)
    return {'scope':'Explicit proposal embedding diagnostic; no runtime proposal source', 'cases':result}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    report=inspect(json.loads(args.input.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,default=asdict)+'\n',encoding='utf-8')


if __name__=='__main__':main()
