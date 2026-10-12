# SPDX-License-Identifier: GPL-3.0-or-later
"""Event-derived planar complex; no embedding optimizer or inferred source planes."""
from collections import defaultdict
from dataclasses import dataclass
from .precision import Scalar, scalar


class KernelFailure(RuntimeError):
    """An implementation failed to complete/validate an admitted Line model."""


class KernelLimit(RuntimeError):
    """Incomplete execution, not an unsupported shape or a selectable prefix."""


@dataclass(frozen=True)
class Vertex:
    xy: tuple[Scalar,Scalar]
    time: Scalar
    sources: tuple[str,...]


@dataclass(frozen=True)
class Patch:
    plane: int
    sources: tuple[str,...]
    loop: tuple[int,...]


@dataclass(frozen=True)
class Event:
    time: Scalar
    contacts: tuple[int,...]
    components_before: int
    components_after: int


@dataclass(frozen=True)
class RoofComplex:
    boundary: object
    intent: object
    frame: object
    planes: tuple
    vertices: tuple[Vertex,...]
    patches: tuple[Patch,...]
    walls: tuple[Patch,...]
    events: tuple[Event,...]
    work: int
    precision: object

    def coordinates(self,*,pitch=.5,eave_height=0.):
        return tuple((self.precision.approximate(v.xy[0]),self.precision.approximate(v.xy[1]),
                      eave_height+pitch*self.precision.approximate(v.time)) for v in self.vertices)

    def inspect(self):
        return {'authority':'global full-Line boundary-conditioned wavefront',
                'sources':[{'id':s.id,'start':s.start,'end':s.end,'role':dict(self.intent.roles)[s.id]}
                           for s in self.boundary.sources],
                'vertices':[{'id':i,'xy':[self.precision.approximate(p) for p in v.xy],
                             'time':self.precision.approximate(v.time),'sources':v.sources}
                            for i,v in enumerate(self.vertices)],
                'patches':[{'plane':p.plane,'sources':p.sources,'loop':p.loop} for p in self.patches],
                'walls':[{'plane':p.plane,'sources':p.sources,'loop':p.loop} for p in self.walls],
                'events':[{'time':self.precision.approximate(e.time),'contacts':e.contacts,
                           'components_before':e.components_before,'components_after':e.components_after}
                          for e in self.events],
                'work':self.work,'predicates':self.precision.inspect()}


class Registry:
    def __init__(self,precision):
        self.precision=precision;self.points=[];self.groups=[];self.parents=[]

    def group(self,time):
        if self.groups and self.precision.compare(self.groups[-1][0],time)==0:return self.groups[-1][1]
        group=[];self.groups.append((time,group));return group

    def register(self,p,time,parents):
        group=self.group(time)
        for i in group:
            old=self.points[i][0]
            if all(self.precision.compare(a,b)==0 for a,b in zip(old,p)):
                self.parents[i].update(parents);return i
        i=len(self.points);self.points.append((p,time));self.parents.append(set(parents));group.append(i)
        return i


def compact(patches,planes,registry,precision):
    """Remove certified degree-two section vertices, retaining event records.

    Every retained patch vertex is on its declared plane. Three vertices on
    the same two independent planes are collinear in space-time. A base edge
    uses the t=0 plane as its second constraint. No coordinates are changed.
    """
    neighbors=defaultdict(set);faces=defaultdict(set)
    for i,patch in enumerate(patches):
        for j,v in enumerate(patch.loop):
            neighbors[v].update((patch.loop[j-1],patch.loop[(j+1)%len(patch.loop)]));faces[v].add(i)
    removable=set()
    for v,adj in neighbors.items():
        if len(adj)!=2:continue
        owners=faces[v];a,b=adj
        if len(owners)==1:
            if any(precision.sign(registry.points[k][1]) for k in (a,v,b)):continue
        elif len(owners)==2:
            first,second=(planes[patches[i].plane] for i in owners)
            if first.role==second.role=='GABLE' and first.normal[0]*second.normal[1]-first.normal[1]*second.normal[0]==0:
                continue
            if (first.normal,first.offset,first.role)==(second.normal,second.offset,second.role):continue
        else:continue
        valid=True
        for i in owners:
            p=planes[patches[i].plane]
            for k in (a,v,b):
                xy,t=registry.points[k]
                residual=sum((xy[j]*p.normal[j] for j in (0,1)),scalar(0))-p.offset-scalar(p.speed)*t
                if precision.sign(residual):valid=False;break
        if valid:removable.add(v)
    output=[]
    for p in patches:
        loop=tuple(v for v in p.loop if v not in removable)
        if len(loop)<3:raise KernelFailure('certified seam suppression exposed a zero-area patch')
        output.append(Patch(p.plane,p.sources,loop))
    return tuple(output)


def patch_cycles(strips,planes,registry,precision):
    from .rotation import cyclic_link
    from .directions import direction,geometry
    parent=list(range(len(strips)));owners={}
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,(plane,loop) in enumerate(strips):
        p=planes[plane];key=(p.normal,p.offset,p.role)
        for a,b in zip(loop,loop[1:]+loop[:1]):
            reverse=(key,b,a)
            if reverse in owners:parent[find(i)]=find(owners[reverse])
            owners[key,a,b]=i
    edges=defaultdict(set);members=defaultdict(set);representative={}
    for i,(plane,loop) in enumerate(strips):
        group=find(i);boundary=edges[group]
        members[group].update(planes[plane].sources);representative[group]=plane
        for a,b in zip(loop,loop[1:]+loop[:1]):
            if (b,a) in boundary:boundary.remove((b,a))
            elif (a,b) in boundary:raise KernelFailure('duplicated oriented swept patch edge')
            else:boundary.add((a,b))
    patches=[]
    for group,boundary in sorted(edges.items()):
        plane=representative[group]
        # Separate touching source regions by their exact planar cyclic link.
        # A wall's natural planar coordinates are (along source, time), since
        # its XY projection has zero area. No diagonal is added to either.
        def project(i):
            p,t=registry.points[i]
            if planes[plane].role=='EAVE':return p
            return sum((p[k]*planes[plane].direction[k] for k in (0,1)),Scalar.number(0)),t
        items=sorted(boundary)
        directions=[]
        for a,b in items:
            ga={geometry(planes[i]) for i in registry.parents[a]}
            gb={geometry(planes[i]) for i in registry.parents[b]}
            common=[p for p in planes if geometry(p) in ga&gb]
            directions.append(direction(planes[plane],common,a,b,registry.points[a][1],registry.points[b][1],project,precision))
        next_edge=cyclic_link(items,directions,precision.sign)
        pending=set(range(len(items)))
        while pending:
            start=min(pending);node=start;loop=[]
            while node in pending:
                loop.append(items[node][0]);pending.remove(node);node=next_edge[node]
            if node!=start:raise KernelFailure('source patch cyclic link joined a traversed region')
            patches.append(Patch(plane,tuple(sorted(members[group])),tuple(loop)))
    return tuple(patches)
