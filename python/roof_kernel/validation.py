# SPDX-License-Identifier: GPL-3.0-or-later
"""Completed source shell incidence and base-boundary coverage certificates.

RoofComplex contains inclined patches and separate stationary wall patches.
The complete source shell has its one boundary at t=0; no base face is added.
Positive oriented inclined patches and this boundary have projection degree 1.
Independent tests additionally check polygon unions and numerical plane fitting.
"""
from collections import defaultdict,Counter
from fractions import Fraction as Q
from functools import cmp_to_key
from .boundary import point,sub,dot,cross
from .precision import scalar
from .complex import KernelFailure
from .directions import direction,geometry


def _connected(adjacency):
    if not adjacency:return False
    seen=set();pending=[next(iter(adjacency))]
    while pending:
        v=pending.pop()
        if v not in seen:seen.add(v);pending.extend(adjacency[v]-seen)
    return len(seen)==len(adjacency)


def _rational(value):
    if not value.numerator.terms:return Q(0)
    if len(value.numerator.terms)==1 and value.numerator.terms[0][0]==1 and \
       value.denominator.terms==((Q(1),Q(1)),):return value.numerator.terms[0][1]
    raise KernelFailure('base boundary did not retain exact rational coordinates')


def simple_cycle(loop,vectors,project,precision):
    """Certify nonadjacent segments neither cross nor touch in patch coordinates.

    Use source-derived edge tangents: products of three unrelated event-time
    quotients are unnecessary for this orientation predicate.
    """
    points=[project(v) for v in loop]
    n=len(loop)
    def side(i,p):
        a=points[i];v=vectors[i]
        return precision.sign(scalar(v[0])*(p[1]-a[1])-scalar(v[1])*(p[0]-a[0]))
    def on(i,p):
        v=vectors[i];a,b=points[i],points[(i+1)%n]
        # direction() oriented the tangent along a -> b.
        along=lambda x:sum((scalar(v[k])*(x[k]-a[k]) for k in (0,1)),scalar(0))
        value=along(p)
        return precision.sign(value)>=0 and precision.compare(value,along(b))<=0
    for i in range(n):
        for j in range(i+1,n):
            if j in ((i+1)%n,(i-1)%n):continue
            a,b=side(i,points[j]),side(i,points[(j+1)%n])
            c,d=side(j,points[i]),side(j,points[(i+1)%n])
            if (a*b<0 and c*d<0) or any(s==0 and on(edge,p) for s,edge,p in (
                (a,i,points[j]),(b,i,points[(j+1)%n]),(c,j,points[i]),(d,j,points[(i+1)%n]))):
                raise KernelFailure('source patch boundary self-crosses or touches')


def validate(complex):
    precision=complex.precision
    faces=complex.patches+complex.walls
    if not faces:raise KernelFailure('completed front has no source patches')
    incidence=defaultdict(list);links=defaultdict(lambda:defaultdict(Counter));face_neighbors=defaultdict(set)
    used=set()
    for i,patch in enumerate(faces):
        if len(patch.loop)<3 or len(set(patch.loop))!=len(patch.loop):
            raise KernelFailure('source patch cycle is incomplete or pinched')
        plane=complex.planes[patch.plane]
        def project(index):
            vertex=complex.vertices[index]
            if plane.role=='EAVE':return vertex.xy
            return sum((vertex.xy[k]*plane.direction[k] for k in (0,1)),scalar(0)),vertex.time
        def cmp(a,b):
            x,y=project(a),project(b)
            return precision.compare(x[0],y[0]) or precision.compare(x[1],y[1])
        minimum=min(patch.loop,key=cmp_to_key(cmp));j=patch.loop.index(minimum)
        source_geometry={sid:geometry(p) for p in complex.planes for sid in p.sources}
        def vector(a,b):
            common={source_geometry[s] for s in complex.vertices[a].sources}& \
                   {source_geometry[s] for s in complex.vertices[b].sources}
            candidates=[p for p in complex.planes if geometry(p) in common]
            return direction(plane,candidates,a,b,complex.vertices[a].time,complex.vertices[b].time,project,precision)
        vectors=[vector(a,b) for a,b in zip(patch.loop,patch.loop[1:]+patch.loop[:1])]
        simple_cycle(patch.loop,vectors,project,precision)
        previous=vector(patch.loop[j-1],minimum);following=vector(minimum,patch.loop[(j+1)%len(patch.loop)])
        turn=scalar(previous[0])*scalar(following[1])-scalar(previous[1])*scalar(following[0])
        offset=1
        while precision.sign(turn)==0 and offset<len(patch.loop):
            offset+=1
            previous=vector(patch.loop[(j-offset)%len(patch.loop)],minimum)
            following=vector(minimum,patch.loop[(j+offset)%len(patch.loop)])
            turn=scalar(previous[0])*scalar(following[1])-scalar(previous[1])*scalar(following[0])
        if precision.sign(turn)<=0:raise KernelFailure('source patch lacks positive oriented planar area')
        for k,index in enumerate(patch.loop):
            used.add(index);vertex=complex.vertices[index]
            local=tuple((vertex.xy[axis]-complex.frame.origin[axis])/complex.frame.scale for axis in (0,1))
            time=vertex.time/complex.frame.scale
            residual=sum((local[k]*plane.normal[k] for k in (0,1)),scalar(0))-plane.offset-scalar(plane.speed)*time
            if precision.sign(residual)!=0:raise KernelFailure('event vertex moved off its declared source plane')
            if precision.sign(time)<0:raise KernelFailure('negative event time')
            a,b=patch.loop[k-1],patch.loop[(k+1)%len(patch.loop)]
            links[index][a][b]+=1;links[index][b][a]+=1
        for a,b in zip(patch.loop,patch.loop[1:]+patch.loop[:1]):incidence[tuple(sorted((a,b)))].append((i,a,b))
    boundary=defaultdict(set);coverage=defaultdict(list)
    for pair,entries in incidence.items():
        if len(entries)==2:
            (i,a,b),(j,c,d)=entries
            if (a,b)!=(d,c):raise KernelFailure('source patches have inconsistent shared edge orientation')
            face_neighbors[i].add(j);face_neighbors[j].add(i)
        elif len(entries)==1:
            _,a,b=entries[0]
            boundary[a].add(b);boundary[b].add(a)
            va,vb=complex.vertices[a],complex.vertices[b]
            if precision.sign(va.time)!=0 or precision.sign(vb.time)!=0:
                raise KernelFailure('complete source shell has a non-base open boundary')
            p,q=tuple(_rational(x) for x in va.xy),tuple(_rational(x) for x in vb.xy)
            edge_vector=sub(q,p);length=dot(edge_vector,edge_vector)
            if not length:raise KernelFailure('zero-length boundary edge')
            intervals=[]
            for source in complex.boundary.sources:
                s,t=point(source.start),point(source.end)
                if cross(edge_vector,sub(s,p)) or cross(edge_vector,sub(t,p)):continue
                x,y=sorted((dot(sub(s,p),edge_vector)/length,dot(sub(t,p),edge_vector)/length))
                lo,hi=max(Q(0),x),min(Q(1),y)
                if lo>=hi:continue
                intervals.append((lo,hi))
                ds=sub(t,s);size=dot(ds,ds)
                ends=tuple(tuple(p[k]+v*edge_vector[k] for k in (0,1)) for v in (lo,hi))
                coverage[source.id].append(tuple(sorted(dot(sub(e,s),ds)/size for e in ends)))
            previous=Q(0)
            for lo,hi in sorted(intervals):
                if lo!=previous:raise KernelFailure('base boundary leaves the original source path')
                previous=hi
            if previous!=1:raise KernelFailure('base boundary lacks source interval coverage')
        else:raise KernelFailure('nonmanifold source shell edge')
    if any(len(adj)!=2 for adj in boundary.values()) or not _connected(boundary):
        raise KernelFailure('source shell does not have one exterior boundary')
    if len(faces)>1 and not _connected(face_neighbors):raise KernelFailure('disconnected source patches')
    if len(used)-len(incidence)+len(faces)!=1:raise KernelFailure('completed source shell is not an Euler disk')
    for vertex,link in links.items():
        degrees=[sum(v.values()) for v in link.values()]
        adjacency={k:set(v) for k,v in link.items()}
        if not _connected(adjacency) or any(d not in (1,2) for d in degrees) or \
           degrees.count(1)!=(2 if vertex in boundary else 0):raise KernelFailure('nonmanifold source vertex link')
    for source in complex.boundary.sources:
        previous=Q(0)
        for lo,hi in sorted(coverage[source.id]):
            if lo!=previous:raise KernelFailure('original source boundary has a gap or overlap')
            previous=hi
        if previous!=1:raise KernelFailure('original source boundary is not completely owned')
    return {'vertices':len(used),'edges':len(incidence),'patches':len(faces),'euler':1,'boundary_cycles':1}
