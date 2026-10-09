# SPDX-License-Identifier: GPL-3.0-or-later
"""Trace relocated gable ends to declared source facets, without roof repair."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    payload=args.report.read_bytes()
    if args.report.suffix=='.gz':payload=gzip.decompress(payload)
    data=json.loads(payload);rows=[]
    for source in data['rows']:
        if 'graph' not in source:continue
        graph=source['graph'];outline=graph['outline'];n=len(outline)
        def line(edge):
            a,b=outline[edge],outline[(edge+1)%n]
            dx,dy=b[0]-a[0],b[1]-a[1];size=math.hypot(dx,dy)
            normal=(-dy/size,dx/size)
            return (*normal,sum(x*y for x,y in zip(normal,a)))
        conflicts=[]
        for node,vertex in enumerate(graph['vertices']):
            if vertex['role']!='ridge_end' or vertex['boundary'] is None:continue
            edge=vertex['boundary']['edge']
            expected=[line((edge-1)%n),line((edge+1)%n)]
            extra=[f['support'] for f in graph['faces'] if node in f['loop'] and
                   not any(math.dist(line(f['support']),value)<1e-8 for value in expected)]
            if extra:
                conflicts.append({'node':node,'cap_edge':edge,'additional_source_supports':extra})
        rows.append({'name':source['name'],'category':source.get('category'),
                     'stage':source['stage'],'embedded':source['embedded'],'cap_conflicts':conflicts})
    result={'scope':__doc__,'input_sha256':hashlib.sha256(payload).hexdigest(),
            'graph_inputs':len(rows),'cap_conflict_inputs':sum(bool(r['cap_conflicts']) for r in rows),
            'conflicts_by_stage':dict(Counter(r['stage'] for r in rows if r['cap_conflicts'])),
            'interpretation':'additional facets violate the simple two-bisector terminal adjustment domain; no arbitrary-embedding impossibility claim',
            'rows':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print({k:v for k,v in result.items() if k not in ('rows','scope')})


if __name__=='__main__':main()
