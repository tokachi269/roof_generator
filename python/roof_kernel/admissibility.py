# SPDX-License-Identifier: GPL-3.0-or-later
"""Necessary source coverage with rational nonexistence certificates.

Triangle/half-plane clipping is a feasibility proof only. It produces no roof,
no roof topology and no candidate scoring. Passing it is not admissibility proof.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from .boundary import area, cross, sub, dot


class InconsistentIntent(ValueError):
    def __init__(self,message,certificate):
        super().__init__(message);self.certificate=certificate


def triangles(ring):
    ids=list(range(len(ring)))
    while len(ids)>3:
        for j,b in enumerate(ids):
            a,c=ids[j-1],ids[(j+1)%len(ids)]
            if cross(sub(ring[b],ring[a]),sub(ring[c],ring[b]))<=0:continue
            edges=((a,b),(b,c),(c,a))
            if any(all(cross(sub(ring[v],ring[u]),sub(ring[k],ring[u]))>=0 for u,v in edges)
                   for k in ids if k not in (a,b,c)):continue
            yield tuple(ring[k] for k in (a,b,c));ids.pop(j);break
        else:raise RuntimeError('exact feasibility triangulation did not find an ear')
    yield tuple(ring[k] for k in ids)


def _clip(ring,plane):
    result=[]
    for a,b in zip(ring,ring[1:]+ring[:1]):
        da,db=dot(plane.normal,a)-plane.offset,dot(plane.normal,b)-plane.offset
        if da<=0:result.append(a)
        if (da<0<db) or (db<0<da):
            t=da/(da-db)
            result.append(tuple(a[k]+t*(b[k]-a[k]) for k in (0,1)))
    return tuple(result)


def necessary_coverage(ring,planes,frame):
    eaves=tuple(p for p in planes if p.role=='EAVE')
    for triangle in triangles(ring):
        region=triangle
        for plane in eaves:
            region=_clip(region,plane)
            if len(region)<3:break
        if len(region)>=3 and area(region)>0:
            witness=tuple(sum(p[k] for p in region)/len(region) for k in (0,1))
            distances=tuple(dot(p.normal,witness)-p.offset for p in eaves)
            if not all(d<0 for d in distances):continue
            world=tuple(witness[k]*frame.scale+frame.origin[k] for k in (0,1))
            certificate={'kind':'no_nonnegative_source_plane','point':tuple(str(v) for v in world),
                         'sources':tuple(p.sources for p in eaves),
                         'unnormalized_signed_values':tuple(str(v) for v in distances)}
            raise InconsistentIntent('no roof above the common eave height at the certified interior point',certificate)
