# SPDX-License-Identifier: GPL-3.0-or-later
"""Oriented planar cyclic link; one operation for fronts and source patches."""
from collections import defaultdict
from functools import cmp_to_key
from .complex import KernelFailure


def compare_vectors(a,b,sign):
    ax,ay=sign(a[0]),sign(a[1]);bx,by=sign(b[0]),sign(b[1])
    ha=0 if ay>0 or (ay==0 and ax>=0) else 1
    hb=0 if by>0 or (by==0 and bx>=0) else 1
    if ha!=hb:return -1 if ha<hb else 1
    c=sign(a[0]*b[1]-a[1]*b[0])
    return -c


def cyclic_link(edges,directions,sign):
    outgoing=defaultdict(list)
    for i,(a,b) in enumerate(edges):outgoing[a].append(i)
    successor={}
    for i,(a,b) in enumerate(edges):
        choices=outgoing[b]
        if not choices:raise KernelFailure('oriented contact boundary has a dangling fragment')
        if len(choices)==1:
            successor[i]=choices[0];continue
        reverse=tuple(-v for v in directions[i])
        ordered=sorted(choices,key=cmp_to_key(lambda x,y:compare_vectors(directions[x],directions[y],sign)))
        before=[k for k in ordered if compare_vectors(directions[k],reverse,sign)<0]
        successor[i]=before[-1] if before else ordered[-1]
    if len(set(successor.values()))!=len(edges):
        raise KernelFailure('cyclic link does not pair every oriented fragment exactly once')
    return successor
