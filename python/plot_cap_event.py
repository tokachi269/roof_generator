# SPDX-License-Identifier: GPL-3.0-or-later
"""Draw raw and converted incidence; coordinates are seeds, not solved meshes."""
import argparse
import gzip
import json
from pathlib import Path


def load(path):
    raw=path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('trace','before','after','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--category',required=True)
    parser.add_argument('--name',required=True)
    args=parser.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    def row(data):
        matches=[r for r in data['rows'] if r['name']==args.name and r.get('category')==args.category]
        if len(matches)!=1:raise ValueError('expected one explicitly identified input')
        return matches[0]
    trace=row(load(args.trace))['trace']
    before,after=(row(load(p))['graph'] for p in (args.before,args.after))
    cap=next(c for c in trace['caps'] if len(c['incident_supports'])>3)
    j,k=cap['raw_xy'],cap['midpoint_xy']
    fig,axes=plt.subplots(1,3,figsize=(13,5),layout='constrained')
    views=[(trace['nodes'],[(f,f[0]) for f in trace['faces']],'Raw skeleton: shared event j'),
           ([v['seed'] for v in before['vertices']],[(f['loop'],f['support']) for f in before['faces']],'Old conversion: move all incidence to k'),
           ([v['seed'] for v in after['vertices']],[(f['loop'],f['support']) for f in after['faces']],'Corrected conversion: retain j, add k')]
    for ax,(points,faces,title) in zip(axes,views):
        for loop,support in faces:
            ax.add_patch(Polygon([points[v] for v in loop],closed=True,
                facecolor=plt.get_cmap('tab20')(support/20),edgecolor='#555',alpha=.7))
        ax.autoscale_view();ax.set_aspect('equal');ax.set_title(title,fontsize=10)
        ax.tick_params(labelsize=8);ax.set_xlabel('normalized X');ax.set_ylabel('normalized Y')
        lo,hi=ax.get_xlim();ax.set_xlim(lo-.02,hi+.04)
    for ax in (axes[0],axes[2]):
        ax.scatter([j[0]],[j[1]],c='red',s=30,zorder=10)
        ax.annotate('j',j,xytext=(-10,-16),textcoords='offset points',fontsize=10)
    for ax in (axes[1],axes[2]):
        ax.scatter([k[0]],[k[1]],c='blue',s=30,zorder=10)
        ax.annotate('k',k,xytext=(6,3),textcoords='offset points',fontsize=10)
    fig.suptitle('Terminal event: raw face incidence, inconsistent conversion, corrected RoofGraph',fontsize=12)
    heights=cap['moved_source_heights']
    axes[1].set_xlabel(f'At k: source-plane values {min(heights):.2f} / {max(heights):.2f}',fontsize=9,color='#9b0000')
    axes[2].set_xlabel('Extra facet stays at j; only two slopes meet at k',fontsize=9)
    fig.supxlabel('Source-plane values use unit speed; solver pitch rescales height. Facet colors indicate source supports.',fontsize=9)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(args.output,dpi=140)


if __name__=='__main__':main()
