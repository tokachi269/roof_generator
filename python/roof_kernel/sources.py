# SPDX-License-Identifier: GPL-3.0-or-later
"""Immutable exact supporting lines and trajectories in a binary scale frame."""
from dataclasses import dataclass
from fractions import Fraction as Q
from .boundary import area, point, dot, sub, UnspecifiedModel
from .precision import Surd, Scalar


@dataclass(frozen=True)
class Frame:
    origin: tuple[Q,Q]
    scale: Q
    def world(self,p):return tuple(p[k]*self.scale+self.origin[k] for k in (0,1))


@dataclass(frozen=True)
class Plane:
    normal: tuple[Q,Q]
    offset: Q
    speed: Surd
    sources: tuple[str,...]
    role: str
    @property
    def direction(self):return self.normal[1],-self.normal[0]


@dataclass(frozen=True)
class Affine:
    origin: Q
    velocity: Surd
    def at(self,t):return Scalar(self.origin*t.denominator+self.velocity*t.numerator,t.denominator)


def trajectory(a,b):
    x,y=a.normal;u,v=b.normal
    det=x*v-y*u
    if not det:raise ZeroDivisionError('parallel active supports need cluster resolution')
    return (Affine((a.offset*v-y*b.offset)/det,(a.speed*v-b.speed*y)*Q(1,det)),
            Affine((x*b.offset-a.offset*u)/det,(b.speed*x-a.speed*u)*Q(1,det)))


def prepare(path,intent):
    roles=intent.bind(path)
    raw=tuple(point(p) for p in path.outline)
    origin=raw[0]
    span=max(max(p[k] for p in raw)-min(p[k] for p in raw) for k in (0,1))
    power=span.numerator.bit_length()-span.denominator.bit_length()
    scale=Q(1<<power) if power>=0 else Q(1,1<<(-power))
    if scale<span:scale*=2
    frame=Frame(origin,scale)
    forward=area(raw)>0
    sources=path.sources if forward else tuple(reversed(path.sources))
    blocks=[]
    for source in sources:
        p,q=(point(source.start),point(source.end)) if forward else (point(source.end),point(source.start))
        p,q=(tuple((v-origin[k])/scale for k,v in enumerate(x)) for x in (p,q))
        dx,dy=sub(q,p)
        factor=max(abs(dx),abs(dy))
        normal=(-dy/factor,dx/factor)
        offset=dot(normal,p)
        key=(normal,offset,roles[source.id])
        if blocks and blocks[-1][0]==key:blocks[-1][1].append(source.id)
        else:blocks.append((key,[source.id]))
    if len(blocks)>1 and blocks[0][0]==blocks[-1][0]:
        blocks[0][1][:0]=blocks[-1][1];blocks.pop()
    ordered=sorted(blocks,key=lambda b:tuple(sorted(b[1])))
    planes=tuple(Plane(n,c,Surd.root(dot(n,n)) if role=='EAVE' else Surd(),tuple(sorted(ids)),role)
                 for (n,c,role),ids in ordered)
    ids={tuple(sorted(parents)):i for i,(key,parents) in enumerate(ordered)}
    cycle=tuple(ids[tuple(sorted(parents))] for key,parents in blocks)
    for a,b in zip(cycle,cycle[1:]+cycle[:1]):
        if planes[a].normal==planes[b].normal:
            raise UnspecifiedModel('collinear full-source role transition requires the partial-boundary model')
    ring=tuple(tuple((p[k]-origin[k])/scale for k in (0,1)) for p in raw)
    if not forward:ring=tuple(reversed(ring))
    return frame,planes,(cycle,),ring
