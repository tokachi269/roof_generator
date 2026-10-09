# SPDX-License-Identifier: GPL-3.0-or-later
"""Check declared crease meanings against solved facet normals, read-only."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path


def inspect(row):
    graph, points = row['graph'], row['vertices']
    gradients = []
    for face in graph['faces']:
        loop = [points[v] for v in face['loop']]
        normal = [0.,0.,0.]
        for a,b in zip(loop,loop[1:]+loop[:1]):
            for k in range(3):
                normal[k] += (a[(k+1)%3]-b[(k+1)%3])*(a[(k+2)%3]+b[(k+2)%3])
        gradients.append((-normal[0]/normal[2],-normal[1]/normal[2]))
    disagreements = []
    flat_valleys = []
    for index, edge in enumerate(graph['edges']):
        a,b = edge['vertices']
        kind = edge['kind']
        if kind == 'valley' and max(abs(points[a][2]),abs(points[b][2]))<1e-8:
            flat_valleys.append(index)
        if len(edge['faces']) != 2:
            if kind == 'gable_end' and not any(graph['vertices'][v]['role']=='ridge_end' for v in (a,b)):
                disagreements.append({'edge':index,'declared':kind,'reason':'no boundary ridge end'})
            continue
        i,j = edge['faces']
        loop = graph['faces'][i]['loop']
        if (loop.index(a)+1)%len(loop) != loop.index(b):
            a,b = b,a
        dx,dy = points[b][0]-points[a][0],points[b][1]-points[a][1]
        p,q = gradients[i],gradients[j]
        bend = (q[0]-p[0])*(-dy)+(q[1]-p[1])*dx
        opposed = sum(x*y for x,y in zip(p,q))/(math.hypot(*p)*math.hypot(*q)) < -1+1e-6
        expected = 'ridge' if opposed else ('hip' if bend>0 else 'valley')
        if kind != expected or abs(bend)<1e-10:
            disagreements.append({'edge':index,'declared':kind,'from_solved_slopes':expected,'bend':bend})
        if kind == 'ridge' and abs(points[a][2]-points[b][2])>1e-6:
            disagreements.append({'edge':index,'declared':kind,'reason':'nonlevel ridge'})
    return {'name':row['name'],'category':row.get('category'),
            'semantic_disagreements':disagreements, 'zero_height_valleys':flat_valleys}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    rows=[];inputs={}
    for path in args.reports:
        payload=path.read_bytes()
        if path.suffix=='.gz':payload=gzip.decompress(payload)
        inputs[path.name]=hashlib.sha256(payload).hexdigest()
        rows.extend(inspect(row) for row in json.loads(payload)['rows'] if row['embedded'])
    result={'scope':__doc__,'input_sha256':inputs,'mesh_inputs':len(rows),
            'semantic_failure_inputs':sum(bool(r['semantic_disagreements']) for r in rows),
            'zero_height_valley_inputs':sum(bool(r['zero_height_valleys']) for r in rows),'rows':rows}
    args.output.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print({k:v for k,v in result.items() if k not in ('rows','scope','input_sha256')})


if __name__=='__main__':main()
