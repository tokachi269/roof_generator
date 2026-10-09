# SPDX-License-Identifier: GPL-3.0-or-later
"""Recursive polygon receiver proposals; tree ancestry never implies a junction."""
from collections import deque
from dataclasses import dataclass
from itertools import product
from .footprint import inside,EPS
from .roof_regions import propose_regions,region_boundary
from .errors import UnsupportedRoofError


@dataclass(frozen=True)
class RegionTree:
    region: int  # canonical candidate region index; geometry has one authority
    children: tuple

    def members(self):
        return (self.region,)+tuple(r for child in self.children for r in child.members())

    @property
    def depth(self):
        return 1+max((child.depth for child in self.children),default=0)


@dataclass(frozen=True)
class _Receiver:
    boundary: tuple
    children: tuple

    def outlines(self):
        return (self.boundary,)+tuple(r for child in self.children for r in child.outlines())


@dataclass(frozen=True)
class RecursiveRegions:
    proposals: tuple
    structures: tuple  # (proposal geometry ID, RegionTree); all distinct ancestry retained
    complete: bool
    work: int
    reason: str | None = None


def recursive_regions(fp,*,max_work=65536,max_candidates=4096,provenance=None):
    if not fp.orthogonal:raise UnsupportedRoofError('recursive region family requires orthogonal input')
    if max_work<1 or max_candidates<1:raise ValueError('positive recursive search budgets required')
    xs,ys=(sorted({p[k] for p in fp.vertices}) for k in (0,1))
    nx,ny=len(xs)-1,len(ys)-1
    work=0;complete=True;reason=None
    def step():
        nonlocal work,complete,reason
        work+=1
        if work>max_work:
            complete=False;reason='recursive region work budget exhausted';return False
        return True
    if nx*ny>max_work:return RecursiveRegions((),(),False,0,'recursive region work budget exhausted')
    occupied=set()
    for i in range(nx):
        for j in range(ny):
            if not step():return RecursiveRegions((),(),False,work,reason)
            if (xs[i+1]-xs[i]>4*EPS and ys[j+1]-ys[j]>4*EPS
                and inside(((xs[i]+xs[i+1])/2,(ys[j]+ys[j+1])/2),fp.vertices)):
                occupied.add((i,j))
    def rectangle(a,b,c,d):return frozenset((i,j) for i in range(a,b) for j in range(c,d))
    def ring(a,b,c,d):
        return tuple(fp.frame.world_xy(p) for p in
                     ((xs[a],ys[c]),(xs[b],ys[c]),(xs[b],ys[d]),(xs[a],ys[d])))
    def components(points):
        remaining=set(points);result=[]
        while remaining:
            seed=min(remaining);remaining.remove(seed);pending=deque((seed,));part={seed}
            while pending:
                if not step():return ()
                i,j=pending.popleft()
                for node in ((i-1,j),(i+1,j),(i,j-1),(i,j+1)):
                    if node in remaining:
                        remaining.remove(node);part.add(node);pending.append(node)
            result.append(frozenset(part))
        return tuple(result)
    def visit(points):
        nonlocal complete,reason
        if not complete:return ()
        a=min(i for i,j in points);b=max(i for i,j in points)+1
        c=min(j for i,j in points);d=max(j for i,j in points)+1
        if len(points)==(b-a)*(d-c):return (_Receiver(ring(a,b,c,d),()),)
        results=[]
        for x0 in range(a,b):
            for x1 in range(x0+1,b+1):
                for y0 in range(c,d):
                    for y1 in range(y0+1,d+1):
                        if not step():return tuple(results)
                        box=rectangle(x0,x1,y0,y1)
                        if not box<=points:continue
                        if any(0<=lo<hi<=nx and 0<=bottom<top<=ny and
                               rectangle(lo,hi,bottom,top)<=points
                               for lo,hi,bottom,top in
                               ((x0-1,x1,y0,y1),(x0,x1+1,y0,y1),
                                (x0,x1,y0-1,y1),(x0,x1,y0,y1+1))):continue
                        residuals=components(points-box)
                        if not complete:return tuple(results)
                        choices=tuple(visit(part) for part in residuals)
                        if not complete:return tuple(results)
                        if any(not options for options in choices):continue
                        for children in product(*choices):
                            if not step():return tuple(results)
                            results.append(_Receiver(ring(x0,x1,y0,y1),children))
                            if len(results)>max_candidates:
                                complete=False;reason='recursive region structure budget exhausted'
                                return tuple(results)
        return tuple(results)
    trees=visit(frozenset(occupied)) if occupied else ()
    # An unfinished recursive search has no selectable structure. In
    # particular, do not perform unbounded canonicalization of a large prefix
    # after the declared search budget has already expired.
    if not complete:return RecursiveRegions((),(),False,work,reason)
    proposals={};structures=[]
    for tree in trees:
        candidate=propose_regions(fp,tree.outlines(),source='recursive_regions',provenance=provenance)
        lookup={region.boundary:i for i,region in enumerate(candidate.regions)}
        def bind(node):
            boundary=region_boundary(fp,node.boundary)
            return RegionTree(lookup[boundary],tuple(bind(child) for child in node.children))
        proposals.setdefault(candidate.id,candidate);structures.append((candidate.id,bind(tree)))
    return RecursiveRegions(tuple(proposals[k] for k in sorted(proposals)),
        tuple(structures),complete,work,reason)
