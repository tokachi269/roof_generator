# SPDX-License-Identifier: GPL-3.0-or-later
"""Show source partition, region model, exterior intent and solved topology."""
import argparse
import gzip
import json
from pathlib import Path
import sys


def load(path):
    raw=path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root',type=Path,required=True)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--limit',type=int,default=4)
    args=parser.parse_args()
    sys.path.insert(0,str(args.code_root/'addon'))
    from roof_generator.core.footprint import analyze
    from roof_generator.core.cells import decompose
    from roof_generator.core.roof_regions import minimum_regions
    from roof_generator.core.receiver_regions import receiver_regions
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    inputs=load(args.inputs)
    records={r['name']:r for r in inputs['inputs']}
    rows=[r for r in load(args.report)['rows'] if r['embedded']][:args.limit]
    if not rows:raise ValueError('no explicit visualization witness')
    fig,axes=plt.subplots(len(rows),4,figsize=(16,4*len(rows)),squeeze=False,layout='constrained')
    colors={'ridge':'#bf263b','hip':'#d2a72b','valley':'#2364ad','eave':'#444','gable_end':'#9934ad'}
    for panels,row in zip(axes,rows):
        fp=analyze(records[row['name']]['footprint']);d=decompose(fp)
        declaration=row['decisions']['intent']
        candidates=(minimum_regions(d),*receiver_regions(fp).proposals)
        region=next(c for c in candidates if c.id==declaration['region_id'])
        for cell in d.cells:
            panels[0].add_patch(Polygon([d.vertices[i] for i in cell.corners],facecolor='#ddd',edgecolor='#777'))
        for index,(support,axis) in enumerate(zip(region.regions,declaration['axes'])):
            for panel in panels[1:3]:
                panel.add_patch(Polygon(support.boundary,facecolor=plt.get_cmap('tab20')(index%20),
                                        edgecolor='#777',alpha=.45))
            lo=[min(p[k] for p in support.boundary) for k in (0,1)]
            hi=[max(p[k] for p in support.boundary) for k in (0,1)]
            center=[(lo[k]+hi[k])/2 for k in (0,1)]
            start=list(center);end=list(center)
            start[axis]-=(hi[axis]-lo[axis])*.32;end[axis]+=(hi[axis]-lo[axis])*.32
            panels[1].annotate('',xy=end,xytext=start,arrowprops={'arrowstyle':'<->','color':'#222'})
            panels[1].text(*center,str(index),fontsize=8)
        for item in declaration['intervals']:
            edge=item['edge'];a=fp.vertices[edge];b=fp.vertices[(edge+1)%len(fp.vertices)]
            points=[tuple(a[k]+t*(b[k]-a[k]) for k in (0,1)) for t in item['interval']]
            panels[2].plot(*zip(*points),color=colors[item['kind']],linewidth=4)
        graph=row['graph'];points=row['vertices']
        for face in graph['faces']:
            panels[3].add_patch(Polygon([points[i][:2] for i in face['loop']],facecolor='#eee',edgecolor='none'))
        for edge in graph['edges']:
            panels[3].plot(*zip(*(points[i][:2] for i in edge['vertices'])),
                           color=colors[edge['kind']],linewidth=1.8)
        titles=('Minimum Cells (analysis)','Region model axes (representative)',
                'Declared exterior eave / gable','Solved RoofGraph: ridge / valley / hip')
        for panel,title in zip(panels,titles):
            panel.set_title(title,fontsize=10);panel.autoscale_view();panel.set_aspect('equal')
            panel.set_xticks([]);panel.set_yticks([])
        panels[0].set_ylabel(row['name'],fontsize=8)
    fig.suptitle('Exterior-only intent witnesses; mixed hip/gable, no architectural ranking',fontsize=13)
    fig.supxlabel('Purple: gable boundary. Red: ridge. Blue: valley. Yellow: hip. Partition lines are not roof junctions.',fontsize=10)
    args.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(args.output,dpi=130)


if __name__=='__main__':main()
