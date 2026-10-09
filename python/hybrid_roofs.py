# SPDX-License-Identifier: GPL-3.0-or-later
"""Declared rectangular roof extensions, composed before the fixed core solve.

This is a diagnostic, not a production backend or fallback. Roof contacts and
axes are chosen before any intersection. Each receiver composes only its own
roof and explicitly attached branch strips. Equal-pitch solid union supplies
the local face intersections; no unrestricted global plane pool is used.
Exact rational clipping avoids jitter, welding thresholds and Boolean repair.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction as Q
from itertools import combinations
import math


class HybridError(ValueError):
    pass


def point(p):
    return tuple(Q(str(x)) for x in p)


def value(plane, p):
    return plane[0]*p[0]+plane[1]*p[1]+plane[2]


def cross(a, b):
    return a[0]*b[1]-a[1]*b[0]


def area(ring):
    return sum(cross(a,b) for a,b in zip(ring,ring[1:]+ring[:1]))/2


def rectangle(box):
    a,b,c,d=box
    return ((a,b),(c,b),(c,d),(a,d))


def clip(ring, plane):
    """Keep the closed nonnegative halfplane, with exact new intersections."""
    result=[]
    for a,b in zip(ring,ring[1:]+ring[:1]):
        u,v=value(plane,a),value(plane,b)
        if u>=0:result.append(a)
        if (u<0<v) or (v<0<u):
            t=u/(u-v)
            result.append(tuple(a[k]+t*(b[k]-a[k]) for k in (0,1)))
    result=tuple(p for i,p in enumerate(result) if i==0 or p!=result[i-1])
    if len(result)>1 and result[0]==result[-1]:result=result[:-1]
    return result if len(result)>=3 and area(result)>0 else ()


def on_segment(p,a,b):
    return cross((p[0]-a[0],p[1]-a[1]),(b[0]-a[0],b[1]-a[1]))==0 and all(
        min(a[k],b[k])<=p[k]<=max(a[k],b[k]) for k in (0,1))


def coordinates(fp, raw):
    """Exact decimal input in the canonical cardinal frame of this experiment.

    The scalar core normalizes in floating point. Recovering its explicit
    source vertex identities avoids treating 1/28 rounded to a decimal as an
    exact length and creating spurious 1e-17 facet slivers. No roof coordinate
    is snapped or perturbed. Non-cardinal inputs remain outside this probe.
    """
    ux,uy=fp.frame.direction
    if (ux,uy) not in ((1.,0.),(-1.,0.),(0.,1.),(0.,-1.)):
        raise HybridError('exact hybrid input probe requires a cardinal frame')
    raw=tuple(point(p) for p in raw)
    if raw[0]==raw[-1]:raw=raw[:-1]
    if any(a[0]!=b[0] and a[1]!=b[1] for a,b in zip(raw,raw[1:]+raw[:1])):
        raise HybridError('exact hybrid input probe requires axis-aligned source edges')
    origin=point(fp.frame.origin);scale=Q(str(fp.frame.scale));u=(Q(ux),Q(uy))
    source=tuple(((p[0]-origin[0])*u[0]+(p[1]-origin[1])*u[1],
                  -(p[0]-origin[0])*u[1]+(p[1]-origin[1])*u[0]) for p in raw)
    source=tuple(tuple(v/scale for v in p) for p in source)
    exact=[]
    for p in fp.vertices:
        matches=[q for q in source if math.dist(tuple(float(x) for x in q),p)<1e-8]
        if len(matches)!=1:raise HybridError('canonical vertex lacks unique original identity')
        exact.append(matches[0])
    maps=[{} for _ in (0,1)]
    for p,q in zip(fp.vertices,exact):
        for k in (0,1):
            if p[k] in maps[k] and maps[k][p[k]]!=q[k]:
                raise HybridError('canonical normalization changed a source coordinate identity')
            maps[k][p[k]]=q[k]
    return tuple(exact),maps


def bounds(candidate, maps=None):
    # These proposals use footprint boundary coordinate identities. Resolve
    # their world/intrinsic roundtrip to that declared grid, not a new snap grid.
    grid=[sorted({p[k] for p in candidate.footprint.vertices}) for k in (0,1)]
    def coordinate(v,k):
        matches=[x for x in grid[k] if abs(x-v)<1e-8]
        if len(matches)!=1:raise HybridError('region lacks unique footprint coordinate identity')
        return maps[k][matches[0]] if maps is not None else Q(str(matches[0]))
    result=[]
    for region in candidate.regions:
        if len(region.boundary)!=4:raise HybridError('nonrectangular local roof model not implemented')
        result.append(tuple(coordinate(fn(p[k] for p in region.boundary),k)
                            for fn,k in ((min,0),(min,1),(max,0),(max,1))))
    return tuple(result)


def contacts(boxes):
    result=[]
    for i,j in combinations(range(len(boxes)),2):
        a,b=boxes[i],boxes[j]
        for axis in (0,1):
            if a[axis+2]!=b[axis] and b[axis+2]!=a[axis]:continue
            other=1-axis
            lo=max(a[other],b[other]);hi=min(a[other+2],b[other+2])
            if lo<hi:result.append((i,j,axis,lo,hi))
    return tuple(result)


def connection(boxes, contact, axes):
    i,j,normal,lo,hi=contact
    a,b=axes
    other=1-normal
    if a==b:
        if a==normal:
            kind='continuation' if (boxes[i][other],boxes[i][other+2])==(boxes[j][other],boxes[j][other+2]) else 'end_contact'
            return (kind,i,j,normal)
        return None
    branch,host=(i,j) if a==normal else (j,i)
    # Do not promote the narrow/wide recommendation to an absolute validity
    # rule. Record widths; the composed surface must still satisfy all eaves.
    return ('extension',branch,host,normal)


def assignments(boxes):
    links=contacts(boxes)
    if len(boxes)>1 and not links:return
    domains={link:tuple((a,b) for a in (0,1) for b in (0,1)
                       if connection(boxes,link,(a,b)) is not None) for link in links}
    if any(not options for options in domains.values()):return
    chosen=[]
    def visit():
        if len(chosen)==len(boxes):
            yield tuple(chosen);return
        for axis in (0,1):
            chosen.append(axis)
            if all(link[1]>=len(chosen) or (chosen[link[0]],chosen[link[1]]) in options
                   for link,options in domains.items()):yield from visit()
            chosen.pop()
    yield from visit()


@dataclass(frozen=True)
class Architecture:
    boxes: tuple
    axes: tuple
    connections: tuple

    @classmethod
    def declare(cls, boxes, axes):
        if len(boxes)!=len(axes) or any(a not in (0,1) for a in axes):
            raise HybridError('one axis per roof region required')
        links=contacts(boxes)
        decisions=[]
        adjacency=defaultdict(set)
        for link in links:
            decision=connection(boxes,link,tuple(axes[i] for i in link[:2]))
            if decision is None:raise HybridError('contact has no declared extension or aligned continuation')
            decisions.append(decision)
            i,j=link[:2];adjacency[i].add(j);adjacency[j].add(i)
        seen=set();pending=[0]
        while pending:
            i=pending.pop()
            if i not in seen:seen.add(i);pending.extend(adjacency[i]-seen)
        if seen!=set(range(len(boxes))):raise HybridError('architecture is disconnected')
        return cls(tuple(boxes),tuple(axes),tuple(decisions))

    def inspect(self):
        widths=[b[3-a]-b[1-a] for b,a in zip(self.boxes,self.axes)]
        return {'boxes':[[float(x) for x in b] for b in self.boxes], 'axes':self.axes,
                'connections':[{'kind':k,'branch':b,'receiver':h,'axis':a,
                                'branch_width':float(widths[b]),'receiver_width':float(widths[h])}
                               for k,b,h,a in self.connections],
                'policy':'equal-pitch union only inside declared receiver strips; no area priority'}


def slopes(box, axis):
    k=1-axis
    vector=[Q(0),Q(0)];vector[k]=Q(1)
    return ((*vector,-box[k]),(*(-v for v in vector),box[k+2]))


def domains(architecture):
    boxes,axes=architecture.boxes,architecture.axes
    planes=[slopes(b,a) for b,a in zip(boxes,axes)]
    extensions=defaultdict(list)
    for kind,branch,host,axis in architecture.connections:
        if kind!='extension':continue
        box=list(boxes[branch])
        # The branch enters the receiving slope and stops there. Extending
        # through the entire receiver would reappear on its opposite slope,
        # creating detached far-side roof fragments rather than an attachment.
        middle=(boxes[host][axis]+boxes[host][axis+2])/2
        if boxes[branch][axis+2]==boxes[host][axis]:
            box[axis]=boxes[host][axis];box[axis+2]=middle
        elif boxes[host][axis+2]==boxes[branch][axis]:
            box[axis]=middle;box[axis+2]=boxes[host][axis+2]
        else:raise HybridError('branch lacks the declared receiver side')
        extensions[host].append((branch,tuple(box)))
    return planes,tuple(((host,box),*extensions[host]) for host,box in enumerate(boxes))


def contact_continuity(architecture, planes, domains):
    """Exact profile proof, before expensive 2D arrangement construction."""
    for i,j,axis,lo,hi in contacts(architecture.boxes):
        first,second=architecture.boxes[i],architecture.boxes[j]
        position=first[axis+2] if first[axis+2]==second[axis] else first[axis]
        local={p for host in (i,j) for member,_ in domains[host] for p in planes[member]}
        cuts={lo,hi}
        for host in (i,j):
            for _,box in domains[host]:
                cuts.update(v for v in (box[1-axis],box[3-axis]) if lo<v<hi)
        for p,q in combinations(local,2):
            line=tuple(p[k]-q[k] for k in range(3))
            if line[1-axis]:
                t=-(line[axis]*position+line[2])/line[1-axis]
                if lo<t<hi:cuts.add(t)
        cuts=sorted(cuts)
        samples=cuts+[ (a+b)/2 for a,b in zip(cuts,cuts[1:]) ]
        for t in samples:
            p=(position,t) if axis==0 else (t,position)
            z=[]
            for host in (i,j):
                active=[m for m,b in domains[host] if all(b[k]<=p[k]<=b[k+2] for k in (0,1))]
                z.append(max(min(value(plane,p) for plane in planes[m]) for m in active))
            if z[0]!=z[1]:raise HybridError('declared contact profiles are discontinuous')


def patches(architecture):
    """One receiver at a time; all its declared branches compose simultaneously."""
    boxes=architecture.boxes
    planes,groups=domains(architecture)
    contact_continuity(architecture,planes,groups)
    output=[]
    for host,box in enumerate(boxes):
        local_domains=groups[host]
        xs=sorted({box[0],box[2],*(v for _,b in local_domains for v in (b[0],b[2]) if box[0]<v<box[2])})
        ys=sorted({box[1],box[3],*(v for _,b in local_domains for v in (b[1],b[3]) if box[1]<v<box[3])})
        for x0,x1 in zip(xs,xs[1:]):
            for y0,y1 in zip(ys,ys[1:]):
                middle=((x0+x1)/2,(y0+y1)/2)
                active=[m for m,b in local_domains if b[0]<middle[0]<b[2] and b[1]<middle[1]<b[3]]
                # All equalities belong to these declared local models. No
                # plane outside this receiver's architecture participates.
                local=sorted({p for m in active for p in planes[m]})
                lines={tuple(a[k]-b[k] for k in range(3)) for a,b in combinations(local,2)
                       if a[:2]!=b[:2]}
                tiles=[rectangle((x0,y0,x1,y1))]
                for line in sorted(lines):
                    split=[]
                    for tile in tiles:
                        signs=[value(line,p) for p in tile]
                        if min(signs)<0<max(signs):
                            split.extend(p for p in (clip(tile,line),clip(tile,tuple(-v for v in line))) if p)
                        else:split.append(tile)
                    tiles=split
                for tile in tiles:
                    middle=tuple(sum(p[k] for p in tile)/len(tile) for k in (0,1))
                    choices=[]
                    for member in active:
                        plane=min(planes[member],key=lambda p:value(p,middle))
                        choices.append((value(plane,middle),plane,member))
                    height=max(x[0] for x in choices)
                    winners=[x for x in choices if x[0]==height]
                    if len({x[1] for x in winners})!=1:
                        raise HybridError('interior patch has ambiguous intersecting surface')
                    output.append((winners[0][1],tile,tuple(sorted(x[2] for x in winners))))
    return output


def merge(pieces):
    """Node exact patch incidences and cancel only coplanar shared segments."""
    vertices={p for _,ring,_ in pieces for p in ring}
    groups=defaultdict(list)
    for plane,ring,owners in pieces:
        cycle=[]
        for a,b in zip(ring,ring[1:]+ring[:1]):
            k=0 if a[0]!=b[0] else 1
            nodes=sorted((p for p in vertices if on_segment(p,a,b)),key=lambda p:(p[k]-a[k])/(b[k]-a[k]))
            cycle.extend(nodes[:-1])
        groups[plane].append((tuple(cycle),owners))
    faces=[]
    for plane,items in sorted(groups.items()):
        neighbors=defaultdict(set);incidence=defaultdict(list)
        for i,(ring,_) in enumerate(items):
            for a,b in zip(ring,ring[1:]+ring[:1]):incidence[tuple(sorted((a,b)))].append(i)
        for owners in incidence.values():
            if len(owners)==2:
                i,j=owners;neighbors[i].add(j);neighbors[j].add(i)
            elif len(owners)>2:raise HybridError('coplanar patches overlap')
        remaining=set(range(len(items)))
        while remaining:
            component=set();pending=[min(remaining)]
            while pending:
                i=pending.pop()
                if i not in component:component.add(i);pending.extend(neighbors[i]-component)
            remaining-=component
            edges=set();origins=set()
            for i in sorted(component):
                ring,owners=items[i];origins.update(owners)
                for a,b in zip(ring,ring[1:]+ring[:1]):
                    if (b,a) in edges:edges.remove((b,a))
                    elif (a,b) in edges:raise HybridError('duplicate patch coverage')
                    else:edges.add((a,b))
            # Edge-connected components stay separate even when they meet
            # at a vertex. A connected facet with a hole is rejected.
            outgoing=defaultdict(list)
            for a,b in edges:outgoing[a].append(b)
            if any(len(v)!=1 for v in outgoing.values()):
                raise HybridError('coplanar patch boundary branches')
            start=min(outgoing);ring=[];node=start
            while node not in ring:
                ring.append(node);node=outgoing[node][0]
            if node!=start:raise HybridError('coplanar patch boundary is not a cycle')
            if area(tuple(ring))<=0:raise HybridError('coplanar facet contains a hole')
            if len(ring)!=len(edges):raise HybridError('coplanar facet contains multiple boundary cycles')
            faces.append((plane,tuple(ring),tuple(sorted(origins))))
    return faces


def topology(fp, architecture, graph_api, BoundaryPoint, outline=None):
    faces=merge(patches(architecture))
    outline=outline or tuple(point(p) for p in fp.vertices)
    used=sorted({p for _,ring,_ in faces for p in ring})
    boundary={}
    for p in used:
        for edge,(a,b) in enumerate(zip(outline,outline[1:]+outline[:1])):
            if on_segment(p,a,b):
                k=0 if a[0]!=b[0] else 1
                t=(p[k]-a[k])/(b[k]-a[k])
                if t==1:edge=(edge+1)%len(outline);t=Q(0)
                boundary[p]=BoundaryPoint(edge,float(t));break
    incidence=defaultdict(list)
    for i,(plane,ring,_) in enumerate(faces):
        for a,b in zip(ring,ring[1:]+ring[:1]):incidence[tuple(sorted((a,b)))].append((i,a,b))
    semantics={};heights=defaultdict(set)
    for plane,ring,_ in faces:
        for p in ring:heights[p].add(value(plane,p))
    if any(len(z)!=1 for z in heights.values()):raise HybridError('declared extensions leave a height discontinuity')
    roles={p:'junction' for p in used}
    eaves=defaultdict(set)
    for key,items in incidence.items():
        a,b=key
        if len(items)==1:
            if a not in boundary or b not in boundary:raise HybridError('interior patch edge is unpaired')
            i=items[0][0]
            if heights[a]==heights[b]=={Q(0)}:
                semantics[key]='eave';eaves[i].add(boundary[a].edge if boundary[a].t!=0 or boundary[a].edge==boundary[b].edge else boundary[b].edge)
            else:semantics[key]='gable_end'
        elif len(items)==2:
            (i,a,b),(j,c,d)=items
            if (a,b)!=(d,c):raise HybridError('face intersection lacks opposite oriented incidence')
            p,q=faces[i][0],faces[j][0]
            if p==q:raise HybridError('coplanar seam survived aggregation')
            sign=(q[0]-p[0])*(-(b[1]-a[1]))+(q[1]-p[1])*(b[0]-a[0])
            if not sign:raise HybridError('face intersection has no convexity')
            semantics[key]='ridge' if p[:2]==tuple(-v for v in q[:2]) else 'hip' if sign>0 else 'valley'
        else:raise HybridError('face intersection is nonmanifold')
    # Remove straight subdivision nodes symmetrically, retaining every input
    # corner and every true junction. This does not select a different model.
    neighbors=defaultdict(set)
    for a,b in incidence:neighbors[a].add(b);neighbors[b].add(a)
    redundant=set()
    for p,adjacent in neighbors.items():
        if len(adjacent)!=2 or p in outline:continue
        a,b=sorted(adjacent)
        if on_segment(p,a,b):redundant.add(p)
    if redundant:
        faces=[(plane,tuple(p for p in ring if p not in redundant),owners) for plane,ring,owners in faces]
    used=sorted({p for _,ring,_ in faces for p in ring});ids={p:i for i,p in enumerate(used)}
    loops=[];sem={};locations={};roles=[]
    final_incidence=Counter(tuple(sorted((a,b))) for _,ring,_ in faces
                            for a,b in zip(ring,ring[1:]+ring[:1]))
    support_options=[]
    for plane,ring,owners in faces:
        matching=[]
        for edge,(a,b) in enumerate(zip(outline,outline[1:]+outline[:1])):
            dx,dy=b[0]-a[0],b[1]-a[1]
            size=abs(dx)+abs(dy)
            normal=(-dy/size,dx/size)
            if plane[:2]==normal and value(plane,a)==0:matching.append(edge)
        if not matching:raise HybridError('composed face has no exterior supporting eave line')
        owned=[]
        for a,b in zip(ring,ring[1:]+ring[:1]):
            midpoint=tuple((a[k]+b[k])/2 for k in (0,1))
            if final_incidence[tuple(sorted((a,b)))]==1:
                z=value(plane,midpoint)
                kind='eave' if z==0 else 'gable_end'
                for edge in matching:
                    if on_segment(midpoint,outline[edge],outline[(edge+1)%len(outline)]):owned.append(edge)
            else:
                candidates=[other for other,loop,_ in faces if other!=plane and a in loop and b in loop]
                if len(candidates)!=1:raise HybridError('simplified crease has ambiguous face pair')
                q=candidates[0]
                sign=(q[0]-plane[0])*(-(b[1]-a[1]))+(q[1]-plane[1])*(b[0]-a[0])
                kind='ridge' if plane[:2]==tuple(-v for v in q[:2]) else 'hip' if sign>0 else 'valley'
            key=tuple(sorted((ids[a],ids[b])))
            if key in sem and sem[key]!=kind:raise HybridError('inconsistent crease meaning')
            sem[key]=kind
        support_options.append(matching)
        loops.append((tuple(ids[p] for p in ring),tuple(sorted(set(owned)))))
    actual_eaves={edge for _,owned in loops for edge in owned}
    resolved=[]
    for (loop,owned),options in zip(loops,support_options):
        support=next((edge for edge in options if edge in actual_eaves),None)
        if support is None:raise HybridError('composed face has no surviving exterior eave on its support line')
        resolved.append(graph_api.RoofFace(loop,(0,),owned,support))
    loops=resolved
    for p in used:
        if p in boundary:
            locations[ids[p]]=boundary[p]
            if heights[p]=={Q(0)}:roles.append('corner')
            elif any(sem.get(tuple(sorted((ids[p],ids[q]))))=='ridge' for q in used if q!=p):roles.append('ridge_end')
            else:roles.append('junction')
        else:roles.append('junction')
    graph=graph_api.make_graph(fp.vertices,fp.source_edges,
        tuple(tuple(float(v) for v in p) for p in used),locations,tuple(roles),loops,sem,'gable')
    return graph, {'architecture':architecture.inspect(),'facet_member_provenance':[list(owners) for _,_,owners in faces],
                  'construction':'exact local solid union of declared receiver/branch domains; fixed graph before solve'}
