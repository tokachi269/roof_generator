# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded maximal receiver polygons with explicitly rectangular residual leaves."""
from collections import deque
from dataclasses import dataclass
from .footprint import inside,EPS
from .roof_regions import propose_regions
from .errors import UnsupportedRoofError


@dataclass(frozen=True)
class ReceiverRegions:
    proposals: tuple
    complete: bool
    work: int
    reason: str | None = None


def receiver_regions(fp,*,max_work=65536,max_candidates=4096,provenance=None):
    if not fp.orthogonal:
        raise UnsupportedRoofError('receiver region family requires an orthogonal footprint')
    if max_work<1 or max_candidates<1:raise ValueError('positive receiver search budgets required')
    xs,ys=(sorted({p[k] for p in fp.vertices}) for k in (0,1))
    nx,ny=len(xs)-1,len(ys)-1
    if nx*ny>max_work:
        return ReceiverRegions((),False,0,'receiver region work budget exhausted')
    occupied={(i,j) for i in range(nx) for j in range(ny)
              if xs[i+1]-xs[i]>4*EPS and ys[j+1]-ys[j]>4*EPS and
              inside(((xs[i]+xs[i+1])/2,(ys[j]+ys[j+1])/2),fp.vertices)}
    prefix=[[0]*(ny+1) for _ in range(nx+1)]
    for i in range(nx):
        for j in range(ny):
            prefix[i+1][j+1]=prefix[i][j+1]+prefix[i+1][j]-prefix[i][j]+int((i,j) in occupied)
    def contained(a,b,c,d):
        return (a>=0 and b<=nx and c>=0 and d<=ny and
                prefix[b][d]-prefix[a][d]-prefix[b][c]+prefix[a][c]==(b-a)*(d-c))
    def ring(a,b,c,d):
        return tuple(fp.frame.world_xy(p) for p in
                     ((xs[a],ys[c]),(xs[b],ys[c]),(xs[b],ys[d]),(xs[a],ys[d])))
    proposals={};work=nx*ny
    for a in range(nx):
        for b in range(a+1,nx+1):
            for c in range(ny):
                for d in range(c+1,ny+1):
                    work+=1
                    if work>max_work:return ReceiverRegions(tuple(proposals.values()),False,work,'receiver region work budget exhausted')
                    if not contained(a,b,c,d):continue
                    if any(contained(*box) for box in
                           ((a-1,b,c,d),(a,b+1,c,d),(a,b,c-1,d),(a,b,c,d+1))):continue
                    remaining=occupied-{(i,j) for i in range(a,b) for j in range(c,d)}
                    leaves=[]
                    while remaining:
                        seed=min(remaining);remaining.remove(seed);pending=deque((seed,));component={seed}
                        while pending:
                            work+=1
                            if work>max_work:return ReceiverRegions(tuple(proposals.values()),False,work,'receiver region work budget exhausted')
                            i,j=pending.popleft()
                            for node in ((i-1,j),(i+1,j),(i,j-1),(i,j+1)):
                                if node in remaining:
                                    remaining.remove(node);component.add(node);pending.append(node)
                        lo=min(i for i,j in component);hi=max(i for i,j in component)+1
                        bottom=min(j for i,j in component);top=max(j for i,j in component)+1
                        if len(component)!=(hi-lo)*(top-bottom):leaves=None;break
                        leaves.append(ring(lo,hi,bottom,top))
                    if leaves is None:continue
                    candidate=propose_regions(fp,(ring(a,b,c,d),*leaves),source='receiver_regions',provenance=provenance)
                    proposals.setdefault(candidate.id,candidate)
                    if len(proposals)>max_candidates:
                        return ReceiverRegions(tuple(proposals.values()),False,work,'receiver region candidate budget exhausted')
    return ReceiverRegions(tuple(proposals[k] for k in sorted(proposals)),True,work)
