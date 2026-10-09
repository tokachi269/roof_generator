# SPDX-License-Identifier: GPL-3.0-or-later
"""Read recorded Cell provenance, actual Parts and solved feature causes."""
import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape
from xml.etree import ElementTree


def diagram(case,roof):
    d=case['provenance_partition'];nodes=d['vertices']
    low=tuple(min(p[k] for p in nodes) for k in (0,1))
    scale=320/max(max(p[k] for p in nodes)-low[k] for k in (0,1))
    colors=('#d9e9fa','#f8e3ce','#dcefd8','#eadcf5','#faedbb')
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="900" viewBox="0 0 1440 900">',
         '<rect width="1440" height="900" fill="white"/>',
         '<g font-family="sans-serif" font-size="14" fill="#17212b">',
         f'<text x="30" y="25">{escape(case["name"])}: recorded authority, not inferred roof semantics</text>']
    def point(p,panel):return (40+panel*480+(p[0]-low[0])*scale,395-(p[1]-low[1])*scale)
    def polygon(ring,panel,color):
        xy=' '.join('%.2f,%.2f'%point(p,panel) for p in ring)
        out.append(f'<polygon points="{xy}" fill="{color}" stroke="#637080" stroke-width="1.5"/>')
    def label(ring,panel,text):
        center=tuple(sum(p[k] for p in ring)/len(ring) for k in (0,1));x,y=point(center,panel)
        out.append(f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="middle">{escape(text)}</text>')
    for panel,title in enumerate(('Minimum Cells (provenance only)','Actual Regions / resolved Parts','Solved graph / recorded feature causes')):
        out.append(f'<text x="{40+panel*480}" y="55">{title}</text>')
    for cell in d['cells']:
        ring=[nodes[i] for i in cell['corners']]
        polygon(ring,0,colors[cell['id']%len(colors)]);label(ring,0,'Cell '+str(cell['id']))
    architecture=roof['architecture']
    owners={m:p['id'] for p in architecture['parts'] for m in p['members']}
    for i,r in enumerate(architecture['region_candidate']['regions']):
        polygon(r['boundary'],1,colors[owners[i]%len(colors)])
        label(r['boundary'],1,f'M{i} / P{owners[i]}')
        source='+'.join(str(c['cell']) for c in r['provenance'])
        out.append(f'<text x="520" y="{455+i*20}">M{i}: intersects source Cell {source}</text>')
    vertices=roof['vertices']
    for face in roof['faces']:polygon([vertices[i] for i in face],2,'#f2eee5')
    ink={'ridge':'#c62035','valley':'#1768c1','hip':'#dc9517','eave':'#777','gable_end':'#777'}
    for edge in roof['graph']['edges']:
        a,b=(point(vertices[i],2) for i in edge['vertices'])
        out.append(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="{ink[edge["kind"]]}" stroke-width="2.5"/>')
    for i,feature in enumerate(roof['features']):
        a,b=(point(vertices[v],2) for v in feature['vertices'])
        out.append(f'<text x="{(a[0]+b[0])/2:.2f}" y="{(a[1]+b[1])/2-4:.2f}">F{i}</text>')
        row=i//2;column=i%2
        cause=(f'F{i} {feature["kind"]}: Parts {feature["parts"]}; members {feature["members"]}; '
               f'{feature["operation"]}; relation {feature["relation"]}')
        out.append(f'<text x="{30+column*705}" y="{565+row*23}">{escape(cause)}</text>')
    out.append('</g></svg>')
    return '\n'.join(out)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    for case in json.loads(args.report.read_text(encoding='utf-8'))['cases']:
        for index,roof in enumerate(case['valid']):
            output=args.output_dir/(case['name']+f'-{index}.svg')
            content=diagram(case,roof)
            output.write_bytes(content.encode())
            render(content,output.with_suffix('.png'))


def render(content,output):
    """Render this code-native diagram for QA; no desktop or image editing."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon,Rectangle
    fig=plt.figure(figsize=(14.4,9),dpi=100)
    axes=fig.add_axes((0,0,1,1));axes.set_xlim(0,1440);axes.set_ylim(900,0);axes.set_axis_off()
    for node in ElementTree.fromstring(content).iter():
        tag=node.tag.split('}')[-1];a=node.attrib
        if tag=='rect':
            axes.add_patch(Rectangle((float(a.get('x',0)),float(a.get('y',0))),
                float(a['width']),float(a['height']),facecolor=a['fill']))
        elif tag=='polygon':
            points=[tuple(map(float,p.split(','))) for p in a['points'].split()]
            axes.add_patch(Polygon(points,facecolor=a['fill'],edgecolor=a['stroke'],linewidth=1))
        elif tag=='line':
            axes.plot((float(a['x1']),float(a['x2'])),(float(a['y1']),float(a['y2'])),
                      color=a['stroke'],linewidth=float(a['stroke-width'])*.75)
        elif tag=='text':
            axes.text(float(a['x']),float(a['y']),node.text,fontsize=10.5,color='#17212b',
                      ha='center' if a.get('text-anchor')=='middle' else 'left',va='baseline')
    fig.savefig(output,dpi=100);plt.close(fig)


if __name__=='__main__':main()
