# SPDX-License-Identifier: GPL-3.0-or-later
"""Enumerate rectangular receivers with rectangular residual leaves.

Diagnostic adaptation of published receiver/leaf models. All coordinate-bounded
receivers are enumerated in the 'all' family, or only inclusion-maximal receivers
in the original 'maximal' probe. Area never ranks ownership. Residual connected
components are declared separate leaves by this proposal family, not repairs of
a Laycock collection owner. Nonrectangular residuals reject this family.
"""
import argparse
from collections import deque
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addon'))
from roof_generator.core.footprint import analyze,inside
from roof_generator.core.roof_regions import propose_regions
from roof_generator.core.region_generation import region_candidates
from roof_generator.core.generation import GenerationSettings


def proposals(fp,receiver_family='maximal'):
    if receiver_family not in ('maximal','all'):
        raise ValueError('unknown receiver hypothesis family')
    xs,ys=(sorted({p[k] for p in fp.vertices}) for k in (0,1))
    occupied={(i,j) for i in range(len(xs)-1) for j in range(len(ys)-1)
              if inside(((xs[i]+xs[i+1])/2,(ys[j]+ys[j+1])/2),fp.vertices)}
    rectangles=[]
    for a in range(len(xs)-1):
        for b in range(a+1,len(xs)):
            for c in range(len(ys)-1):
                for d in range(c+1,len(ys)):
                    cells={(i,j) for i in range(a,b) for j in range(c,d)}
                    if cells<=occupied:rectangles.append((a,b,c,d,cells))
    receivers=(rectangles if receiver_family=='all' else
               [r for r in rectangles if not any(r[4]<other[4] for other in rectangles)])
    accepted=[];rejected=[]
    def ring(a,b,c,d):
        return tuple(fp.frame.world_xy(p) for p in ((xs[a],ys[c]),(xs[b],ys[c]),(xs[b],ys[d]),(xs[a],ys[d])))
    for a,b,c,d,receiver in receivers:
        remaining=occupied-receiver
        leaves=[]
        while remaining:
            seed=min(remaining);pending=deque([seed]);component={seed};remaining.remove(seed)
            while pending:
                i,j=pending.popleft()
                for node in ((i-1,j),(i+1,j),(i,j-1),(i,j+1)):
                    if node in remaining:
                        remaining.remove(node);component.add(node);pending.append(node)
            lo=min(i for i,j in component);hi=max(i for i,j in component)+1
            bottom=min(j for i,j in component);top=max(j for i,j in component)+1
            if component!={(i,j) for i in range(lo,hi) for j in range(bottom,top)}:
                leaves=None;break
            leaves.append(ring(lo,hi,bottom,top))
        if leaves is None:
            rejected.append({'receiver':ring(a,b,c,d),'reason':'nonrectangular residual leaf'});continue
        accepted.append(propose_regions(fp,[ring(a,b,c,d),*leaves],source=receiver_family+'_receiver_probe'))
    return accepted,rejected


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--receiver-family',choices=('maximal','all'),default='maximal')
    args=p.parse_args();rows=[]
    for record in json.loads(args.inputs.read_text(encoding='utf-8'))['inputs']:
        fp=analyze(record['footprint']);family,rejected=proposals(fp,args.receiver_family)
        from roof_generator.core.region_generation import RegionPool
        pool=(region_candidates(family,GenerationSettings(max_axis_assignments=65536))
              if family else RegionPool((),(),True,'no receiver with rectangular residual leaves'))
        row={'name':record['name'],'proposals':[c.inspect() for c in family],
             'rejected_receivers':rejected,'embedded_roofs':len(pool.valid),
             'rejections':sorted({r.stage+': '+r.reason for r in pool.rejected}),
             'complete':pool.complete,'reason':pool.reason}
        rows.append(row);print(row['name'],len(family),'proposals',len(pool.valid),'embedded',flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'scope':__doc__,'receiver_family':args.receiver_family,'cases':rows},indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
