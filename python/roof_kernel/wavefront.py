# SPDX-License-Identifier: GPL-3.0-or-later
"""Source-fragment contact graph at a certified common event time.

Predict vertex/fragment contacts. Node every fragment against every contact,
resolve coincident atomic intervals, then reconnect all surviving chains by
their planar cyclic link. Collapse/split/high-degree contacts use this same
operation; there are no building-shape or junction-template handlers.
"""
from collections import defaultdict
from functools import cmp_to_key
from fractions import Fraction as Q
from .precision import Precision, Surd, Scalar, scalar
from .boundary import dot,cross
from .sources import prepare,trajectory,Plane
from .admissibility import necessary_coverage,InconsistentIntent
from .complex import KernelFailure,KernelLimit,Registry,patch_cycles,compact,Vertex,Event,RoofComplex
from .rotation import cyclic_link


class Wavefront:
    def __init__(self,path,intent,*,max_work=65536,max_bits=4096):
        self.path=path;self.intent=intent
        self.frame,self.planes,self.cycles,self.ring=prepare(path,intent)
        necessary_coverage(self.ring,self.planes,self.frame)
        self.planes=list(self.planes)
        self.precision=Precision(max_bits=max_bits)
        self.registry=Registry(self.precision)
        self.current=Scalar.number(0)
        self.max_work=max_work;self.work=0
        self.trajectories={};self.contacts={};self.strips=[];self.events=[]
        self.positions={}
        self.intervals={};self.subdivisions={}

    def merge_sources(self,a,b):
        p,q=self.planes[a],self.planes[b]
        if (p.normal,p.offset,p.role)!=(q.normal,q.offset,q.role):
            raise KernelFailure('only identical source planes may merge their lineage')
        sources=tuple(sorted(set(p.sources+q.sources)))
        for i,plane in enumerate(self.planes):
            if plane.sources==sources:return i
        self.planes.append(Plane(p.normal,p.offset,p.speed,sources,p.role))
        return len(self.planes)-1

    def tick(self):
        self.work+=1
        if self.work>self.max_work:raise KernelLimit('contact certificate work budget exhausted')

    def vertex(self,a,b):
        key=(a,b)
        if key not in self.trajectories:
            try:self.trajectories[key]=trajectory(self.planes[a],self.planes[b])
            except ZeroDivisionError as exc:raise KernelFailure(str(exc)) from exc
        return self.trajectories[key]

    def at(self,vertex,time):
        key=(id(vertex),id(time))
        if key not in self.positions:self.positions[key]=(vertex,time,tuple(v.at(time) for v in vertex))
        return self.positions[key][2]

    def fragments(self,cycles=None):
        result=[]
        for cycle in self.cycles if cycles is None else cycles:
            for j,p in enumerate(cycle):
                result.append((p,self.vertex(cycle[j-1],p),self.vertex(p,cycle[(j+1)%len(cycle)])))
        return result

    def projected(self,p,plane):
        return sum((p[k]*plane.direction[k] for k in (0,1)),Scalar.number(0))

    def contains(self,p,fragment,time):
        pid,a,b=fragment;plane=self.planes[pid]
        x=self.projected(p,plane)
        key=(pid,id(a),id(b),id(time))
        if key not in self.intervals:
            self.intervals[key]=(time,self.projected(self.at(a,time),plane),self.projected(self.at(b,time),plane))
        _,start,end=self.intervals[key]
        return self.precision.compare(x,start)>=0 and self.precision.compare(end,x)>=0

    def contact_time(self,a,b,c):
        key=(a,b,c)
        if key not in self.contacts:
            v=self.vertex(a,b);p=self.planes[c]
            base=sum(p.normal[k]*v[k].origin for k in (0,1))-p.offset
            speed=sum((v[k].velocity*p.normal[k] for k in (0,1)),Surd())-p.speed
            self.contacts[key]=None if not speed.terms else Scalar(Surd.number(-base),speed)
        return self.contacts[key]

    def next_time(self):
        fragments=self.fragments();result=None
        for cycle in self.cycles:
            for j,b in enumerate(cycle):
                a=cycle[j-1];v=self.vertex(a,b)
                for fragment in fragments:
                    c=fragment[0]
                    if c in (a,b):continue
                    self.tick()
                    t=self.contact_time(a,b,c)
                    if t is None or self.precision.compare(t,self.current)<=0:continue
                    if result is not None and self.precision.compare(t,result)>0:continue
                    if not self.contains(self.at(v,t),fragment,t):continue
                    if result is None or self.precision.compare(t,result)<0:result=t
        if result is None:
            if all(self.planes[p].role=='GABLE' for cycle in self.cycles for p in cycle):
                polygons=[]
                for cycle in self.cycles:
                    points=[]
                    for j,p in enumerate(cycle):
                        v=self.vertex(cycle[j-1],p)
                        points.append(tuple(str(v[k].origin*self.frame.scale+self.frame.origin[k]) for k in (0,1)))
                    polygons.append(points)
                certificate={'kind':'stationary_remaining_front','time':self.precision.approximate(self.current),
                             'cycles':[tuple(self.planes[p].sources for p in cycle) for cycle in self.cycles],
                             'exact_polygons':polygons}
                raise InconsistentIntent('stationary positive-area front cannot complete a finite roof',certificate)
            raise KernelFailure('moving positive-area front has no predicted future contact')
        return result

    def nodes(self,fragments,time):
        group=self.registry.group(time)
        for p,a,b in fragments:
            for v in (a,b):self.registry.register(self.at(v,time),time,(p,))
        return group

    def split(self,fragment,time,group):
        p,a,b=fragment;plane=self.planes[p]
        key=(p,id(a),id(b),id(time),len(group))
        if key in self.subdivisions:return self.subdivisions[key][1]
        result=[]
        for node in group:
            xy=self.registry.points[node][0]
            on_plane=p in self.registry.parents[node]
            if not on_plane:
                value=sum((xy[k]*plane.normal[k] for k in (0,1)),Scalar.number(0))-plane.offset-scalar(plane.speed)*time
                on_plane=self.precision.sign(value)==0
            if on_plane and self.contains(xy,fragment,time):
                self.registry.parents[node].add(p);result.append(node)
        result=sorted(result,key=cmp_to_key(lambda x,y:self.precision.compare(
            self.projected(self.registry.points[x][0],plane),self.projected(self.registry.points[y][0],plane))))
        self.subdivisions[key]=(time,result)
        return result

    def strip(self,fragment,time,lower,upper):
        p,_,_=fragment
        lo=self.split(fragment,self.current,lower)
        hi=self.split(fragment,time,upper)
        loop=[]
        for node in lo+list(reversed(hi)):
            if not loop or node!=loop[-1]:loop.append(node)
        if len(loop)>1 and loop[-1]==loop[0]:loop.pop()
        if len(set(loop))>=3:self.strips.append((p,tuple(loop)))

    def coalesce(self,cycle,time):
        cycle=list(cycle)
        while len(cycle)>2:
            for j,a in enumerate(cycle):
                k=(j+1)%len(cycle);b=cycle[k]
                p,q=self.planes[a],self.planes[b]
                if p.normal!=q.normal:continue
                if self.precision.sign(scalar(p.offset-q.offset)+scalar(p.speed-q.speed)*time)!=0:
                    raise KernelFailure('noncoincident parallel supports became neighbors')
                cmp=self.precision.sign(p.speed-q.speed)
                faster=self.merge_sources(a,b) if cmp==0 else a if cmp>0 else b
                cycle[j]=faster;cycle.pop(k);break
            else:return tuple(cycle)
        return ()

    def resolve(self,fragments,time,group):
        atomic=defaultdict(list)
        for fragment in fragments:
            p=fragment[0];nodes=self.split(fragment,time,group)
            for a,b in zip(nodes,nodes[1:]):atomic[tuple(sorted((a,b)))].append((a,b,p))
        edges=[]
        for items in atomic.values():
            directions={(a,b) for a,b,p in items}
            if len(directions)==2:continue
            chosen=items[0]
            for item in items[1:]:
                cmp=self.precision.sign(self.planes[item[2]].speed-self.planes[chosen[2]].speed)
                if cmp>0:chosen=item
                elif cmp==0:chosen=(chosen[0],chosen[1],self.merge_sources(chosen[2],item[2]))
            edges.append(chosen)
        successor=cyclic_link([(a,b) for a,b,p in edges],
                              [self.planes[p].direction for a,b,p in edges],
                              lambda x:1 if x>0 else -1 if x<0 else 0)
        pending=set(range(len(edges)));cycles=[]
        while pending:
            first=min(pending);i=first;walk=[]
            while i in pending:
                pending.remove(i);walk.append(i);i=successor[i]
            if i!=first:raise KernelFailure('contact links join an already traversed cycle')
            if len(walk)<3:continue
            nodes=[edges[i][0] for i in walk]
            # At the lexicographically extreme vertex, the turn determines
            # bounded-face orientation. Avoid a growing global radical sum
            # for polygon area; the source directions are exact rational rays.
            def cmp(x,y):
                a,b=self.registry.points[x][0],self.registry.points[y][0]
                return self.precision.compare(a[0],b[0]) or self.precision.compare(a[1],b[1])
            extreme=min(nodes,key=cmp_to_key(cmp));j=nodes.index(extreme)
            previous=self.planes[edges[walk[j-1]][2]].direction
            following=self.planes[edges[walk[j]][2]].direction
            turn=cross(previous,following)
            if turn<=0:continue
            cycle=self.coalesce(tuple(edges[i][2] for i in walk),time)
            if cycle:cycles.append(cycle)
        return tuple(cycles)

    def run(self):
        initial=self.fragments();self.nodes(initial,self.current)
        while self.cycles:
            self.tick();time=self.next_time();fragments=self.fragments()
            lower=self.nodes(fragments,self.current);upper=self.nodes(fragments,time)
            for fragment in fragments:self.strip(fragment,time,lower,upper)
            before=len(self.cycles);cycles=self.resolve(fragments,time,upper)
            # Close newly exposed zero-time incidences inside this cluster.
            # A regular state's cyclic signature is unchanged; no event is
            # emitted and no zero-height source strip is materialized here.
            def signature(state):
                return tuple(sorted(min(c[i:]+c[:i] for i in range(len(c))) for c in state))
            while cycles:
                self.tick();current_signature=signature(cycles)
                exposed=self.fragments(cycles);self.nodes(exposed,time)
                updated=self.resolve(exposed,time,upper)
                cycles=updated
                if signature(updated)==current_signature:break
            contacts=tuple(i for i in upper if len(self.registry.parents[i])>=3)
            self.events.append(Event(time,contacts,before,len(cycles)))
            self.cycles=cycles;self.current=time
        patches=patch_cycles(self.strips,self.planes,self.registry,self.precision)
        patches=compact(patches,self.planes,self.registry,self.precision)
        vertices=tuple(Vertex(self.frame.world(p),t*self.frame.scale,
                              tuple(sorted({s for pid in self.registry.parents[i] for s in self.planes[pid].sources})))
                       for i,(p,t) in enumerate(self.registry.points))
        result=RoofComplex(self.path,self.intent,self.frame,tuple(self.planes),vertices,
                           tuple(p for p in patches if self.planes[p.plane].role=='EAVE'),
                           tuple(p for p in patches if self.planes[p.plane].role=='GABLE'),
                           tuple(Event(e.time*self.frame.scale,e.contacts,e.components_before,e.components_after)
                                 for e in self.events),self.work,self.precision)
        from .validation import validate
        validate(result)
        return result


def construct(path,intent,*,max_work=65536,max_bits=4096):
    if isinstance(max_work,bool) or not isinstance(max_work,int) or max_work<1:
        raise ValueError('positive work budget required')
    return Wavefront(path,intent,max_work=max_work,max_bits=max_bits).run()
