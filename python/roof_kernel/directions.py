# SPDX-License-Identifier: GPL-3.0-or-later
"""Patch boundary tangents from incident source equations, not coordinate products."""
from .precision import Surd,scalar
from .boundary import dot,cross
from .complex import KernelFailure


def geometry(plane):return plane.normal,plane.offset,plane.role


def tangent(plane,other):
    if plane.role=='EAVE':
        if other.role=='GABLE':return other.direction
        a,b=plane.normal;c,d=other.normal
        vector=(other.speed*b-plane.speed*d,plane.speed*c-other.speed*a)
        if any(v.terms for v in vector):return vector
    elif other.role=='GABLE':
        if cross(plane.normal,other.normal):return 0,1
    else:
        return other.speed*dot(plane.direction,plane.direction),dot(other.normal,plane.direction)
    return None


def direction(plane,other_planes,a,b,ta,tb,project,precision):
    vector=None
    if precision.compare(ta,tb)==0:
        vector=plane.direction if plane.role=='EAVE' else (1,0)
    else:
        for other in other_planes:
            if geometry(other)==geometry(plane):continue
            vector=tangent(plane,other)
            if vector is not None:break
    if vector is None:raise KernelFailure('source patch edge lacks a source intersection or time section')
    start,end=project(a),project(b)
    along=sum(((end[k]-start[k])*scalar(vector[k]) for k in (0,1)),scalar(0))
    sign=precision.sign(along)
    if not sign:raise KernelFailure('source patch boundary edge has zero length')
    return tuple(v if sign>0 else -v for v in vector)
