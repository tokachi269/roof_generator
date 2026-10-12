# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact full-Line path and explicit role ownership, without roof parts."""
from dataclasses import dataclass
from fractions import Fraction as Q
import math


class InvalidBoundary(ValueError):pass
class InvalidIntent(ValueError):pass
class UnspecifiedModel(ValueError):pass


def point(p):
    if len(p)!=2 or not all(math.isfinite(x) for x in p):raise InvalidBoundary('finite XY required')
    return tuple(Q(x) for x in p)


def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def area(points):return sum(cross(a,b) for a,b in zip(points,points[1:]+points[:1]))/2
def on_segment(p,a,b):
    return cross(sub(b,a),sub(p,a))==0 and dot(sub(p,a),sub(p,b))<=0
def intersects(a,b,c,d):
    if any(on_segment(p,u,v) for p,u,v in ((a,c,d),(b,c,d),(c,a,b),(d,a,b))):return True
    return cross(sub(b,a),sub(c,a))*cross(sub(b,a),sub(d,a))<0 and \
           cross(sub(d,c),sub(a,c))*cross(sub(d,c),sub(b,c))<0


@dataclass(frozen=True)
class Line:
    id: str
    start: tuple[float,float]
    end: tuple[float,float]
    def __post_init__(self):
        if not isinstance(self.id,str) or not self.id:raise InvalidBoundary('nonempty source ID required')
        if point(self.start)==point(self.end):raise InvalidBoundary('zero-length source')
    def evaluate(self,t):
        if not 0<=t<=1:raise ValueError('source parameter outside [0,1]')
        return tuple(a+t*(b-a) for a,b in zip(self.start,self.end))


@dataclass(frozen=True)
class BoundaryPath:
    sources: tuple[Line,...]
    def __post_init__(self):
        if len(self.sources)<3 or not all(isinstance(s,Line) for s in self.sources):
            raise InvalidBoundary('closed full-Line path required')
        if len({s.id for s in self.sources})!=len(self.sources):raise InvalidBoundary('duplicate source ID')
        if any(point(a.end)!=point(b.start) for a,b in zip(self.sources,self.sources[1:]+self.sources[:1])):
            raise InvalidBoundary('discontinuous source path')
        ring=tuple(point(p) for p in self.outline)
        if not area(ring):raise InvalidBoundary('zero-area path')
        for i,a in enumerate(ring):
            b=ring[(i+1)%len(ring)]
            if dot(sub(a,ring[i-1]),sub(b,a))<0 and cross(sub(a,ring[i-1]),sub(b,a))==0:
                raise InvalidBoundary('adjacent boundary backtracks')
            for j in range(i+1,len(ring)):
                if j in ((i+1)%len(ring),(i-1)%len(ring)):continue
                if intersects(a,b,ring[j],ring[(j+1)%len(ring)]):
                    raise InvalidBoundary('self-intersection or touching')
    @property
    def outline(self):return tuple(s.start for s in self.sources)


@dataclass(frozen=True)
class RoofIntent:
    roles: tuple[tuple[str,str],...]
    def bind(self,path):
        mapping=dict(self.roles)
        if len(mapping)!=len(self.roles) or set(mapping)!={s.id for s in path.sources} or \
           any(role not in ('EAVE','GABLE') for role in mapping.values()):
            raise InvalidIntent('complete disjoint full-source EAVE/GABLE roles required')
        if 'EAVE' not in mapping.values():
            from .admissibility import InconsistentIntent
            raise InconsistentIntent('all stationary sources cannot close a finite pitched roof',
                                     {'kind':'no_moving_source','sources':tuple(sorted(mapping))})
        return mapping
