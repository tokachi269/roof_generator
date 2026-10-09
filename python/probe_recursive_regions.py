# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure recursive 2D structures separately from architectural roof coverage."""
import argparse
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addon'))
from roof_generator.core.footprint import analyze
from roof_generator.core.recursive_regions import recursive_regions


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--category')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-work',type=int,default=65536)
    parser.add_argument('--max-candidates',type=int,default=4096)
    args=parser.parse_args();raw=args.inputs.read_bytes()
    data=json.loads(gzip.decompress(raw) if args.inputs.suffix=='.gz' else raw)
    records=data['corpora'][args.category] if args.category else data['inputs']
    rows=[]
    for i,record in enumerate(records):
        result=recursive_regions(analyze(record['footprint']),max_work=args.max_work,max_candidates=args.max_candidates)
        rows.append({'name':record['name'],'complete':result.complete,'reason':result.reason,
            'work':result.work,'geometry_count':len(result.proposals),'structure_count':len(result.structures),
            'depth':max((tree.depth for identity,tree in result.structures),default=0),
            'structures':[(identity,asdict(tree)) for identity,tree in result.structures] if not args.category else []})
        if (i+1)%10==0:print(i+1,len(records),flush=True)
    report={'scope':'2D region decomposition only; no roof model, end constraints, graph or embedding acceptance',
        'inputs':len(rows),'complete_with_proposals':sum(r['complete'] and r['geometry_count']>0 for r in rows),
        'incomplete':sum(not r['complete'] for r in rows),'rows':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print({k:v for k,v in report.items() if k!='rows'},flush=True)


if __name__=='__main__':main()
