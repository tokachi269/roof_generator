# SPDX-License-Identifier: GPL-3.0-or-later
"""Inspect exact Line complexes and compare convex roles to an independent oracle."""
import argparse
from collections import defaultdict
from html import escape
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from python.audit_line_kernel import record_model,oracle
from python.roof_kernel.wavefront import construct
from python.roof_kernel.mesh import view


def svg(result):
    points=result.coordinates()
    outline=result.boundary.outline
    lo=[min(p[k] for p in outline) for k in (0,1)]
    span=max(max(p[k] for p in outline)-lo[k] for k in (0,1));scale=420/span
    def at(p):return f'{40+(float(p[0])-lo[0])*scale:.5f},{460-(float(p[1])-lo[1])*scale:.5f}'
    data=['<svg xmlns="http://www.w3.org/2000/svg" width="520" height="520" viewBox="0 0 520 520">',
          '<rect width="520" height="520" fill="white"/>']
    palette=('#7bb6cf','#dbab70','#aacb7b','#bd8cb9','#cebe79','#94b7ab')
    for i,p in enumerate(result.patches):
        data.append(f'<polygon points="{" ".join(at(points[v]) for v in p.loop)}" fill="{palette[i%len(palette)]}" fill-opacity=".65" stroke="#333" stroke-width="1.5"><title>{escape(str(p.sources))}</title></polygon>')
    for wall in result.walls:
        data.append(f'<polyline points="{" ".join(at(points[v]) for v in wall.loop)}" fill="none" stroke="#e29322" stroke-dasharray="4 3"><title>stationary patch {escape(str(wall.sources))}</title></polyline>')
    roles=dict(result.intent.roles)
    for source in result.boundary.sources:
        color='#bd3441' if roles[source.id]=='GABLE' else '#206aa7'
        a,b=at(source.start),at(source.end)
        data.append(f'<polyline points="{a} {b}" fill="none" stroke="{color}" stroke-width="3"><title>{escape(source.id)} {roles[source.id]}</title></polyline>')
    for e in result.events:
        for v in e.contacts:
            x,y=at(points[v]).split(',')
            data.append(f'<circle cx="{x}" cy="{y}" r="3" fill="#222"><title>time {result.precision.approximate(e.time):.8g}; {escape(str(result.vertices[v].sources))}</title></circle>')
    data.append('<text x="20" y="505" font-size="12">blue: EAVE; red: GABLE; orange: stationary patches; dots: contacts</text></svg>')
    return '\n'.join(data)


def convex_roles():
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from python.roof_kernel_proof import construct as independent
    shapes=[[(0,0),(9,0),(4,7)],[(0,0),(9,0),(8,6),(1,5)],
            [(0,0),(8,0),(10,4),(5,8),(0,5)],
            [(0,2),(2,0),(7,0),(9,2),(9,6),(7,8),(2,8),(0,6)]]
    total=0
    for points in shapes:
        for mask in range(1,1<<len(points)):
            record={'footprint':points,'roles':['EAVE' if mask&(1<<i) else 'GABLE' for i in range(len(points))]}
            model=record_model(record);actual=construct(*model);expected=independent(*model)
            oracle(actual)
            a=actual.coordinates();b=expected.coordinates();groups=defaultdict(list)
            for patch in actual.patches:
                assert len(patch.sources)==1
                groups[patch.sources[0]].append(Polygon([a[v][:2] for v in patch.loop]))
            reference={p.source:Polygon([b[v][:2] for v in p.loop]) for p in expected.patches}
            assert set(groups)==set(reference)
            for source,polygons in groups.items():
                assert unary_union(polygons).symmetric_difference(reference[source]).area<1e-7
            total+=1
    return {'assignments':total,'source_region_comparison':True,'kernel_failures':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--convex-roles',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    records=json.loads((ROOT/'python/tests/fixtures/kernel_line_construction.json').read_text())['records']
    rows=[]
    for record in records:
        result=construct(*record_model(record));checked=oracle(result)
        mesh=view(result,include_walls=record.get('include_walls',False))
        name=record['name']
        (args.output/f'{name}.json').write_text(json.dumps({'input':record,'complex':result.inspect(),'oracle':checked},indent=2,default=str)+'\n')
        (args.output/f'{name}.svg').write_text(svg(result))
        obj=['v '+' '.join(format(x,'.17g') for x in v) for v in mesh.vertices]
        obj+=['f '+' '.join(str(i+1) for i in face) for face in mesh.faces]
        (args.output/f'{name}.obj').write_text('\n'.join(obj)+'\n')
        rows.append({'name':name,'corners':len(record['footprint']),'vertices':len(mesh.vertices),'faces':len(mesh.faces),
                     'events':len(result.events),'work':result.work,'oracle':checked,'include_walls':record.get('include_walls',False)})
    report={'cases':rows}
    if args.convex_roles:report['independent_convex_roles']=convex_roles()
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
