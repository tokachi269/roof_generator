# SPDX-License-Identifier: GPL-3.0-or-later
"""Complete global roof incidence from resolved exterior intent; no Cell primitives."""
from collections import defaultdict
from dataclasses import dataclass
import math
from . import graph as graph_api
from .footprint import Footprint
from .provenance import BoundaryPoint
from .errors import UnsupportedRoofError
from .roof_intent import opposed_supports, cap_parameter


@dataclass(frozen=True)
class PolygonRoof:
    """Resolved continuous roof model on the actual whole polygon support.

    Every exterior edge is explicitly an eave or a gable end. There are no
    internal Cell caps or partition-derived junction obligations. Rectangle
    interpretations may guide these ends, but are not independent roof parts.
    """
    footprint: Footprint
    gable_edges: tuple[int, ...]
    roof_type: str = 'gable'

    def __post_init__(self):
        n = len(self.footprint.vertices)
        if self.roof_type not in ('gable','hip') or \
           (self.roof_type == 'gable' and not self.gable_edges) or \
           (self.roof_type == 'hip' and self.gable_edges) or \
           tuple(sorted(set(self.gable_edges))) != self.gable_edges or \
           any(isinstance(e,bool) or not isinstance(e,int) or not 0<=e<n for e in self.gable_edges):
            raise UnsupportedRoofError('polygon roof requires explicit gable ends or all-eave hip intent')

    def inspect(self):
        return {'model':('continuous polygon roof with terminal gable ends' if self.roof_type=='gable'
                         else 'continuous polygon roof with all-eave hip intent'),
                'regions':[self.footprint.vertices],
                'ends':[{'edge':e,'shape':'gable' if e in self.gable_edges else 'eave'}
                        for e in range(len(self.footprint.vertices))],
                'authority':'polygon support and resolved exterior ends; no Cell roof primitives'}


def topology(structure, incidence):
    if not isinstance(structure, PolygonRoof):
        raise TypeError('polygon topology requires a resolved PolygonRoof model')
    fp = structure.footprint
    selected_caps = frozenset(structure.gable_edges)
    seeds = list(incidence.points)
    loops = list(incidence.faces)
    n = len(fp.vertices)
    # Bind each face to its explicit initiating exterior edge. Do not rely on
    # the dependency's face order or derive ownership from final solved XYZ.
    supports = []
    for loop in loops:
        a,b = loop[:2]
        if not (a < n and b == (a+1)%n and math.dist(seeds[a],fp.vertices[a])<2e-8):
            raise UnsupportedRoofError('skeleton original-edge identity changed')
        supports.append(a)
    seeds[:n] = fp.vertices
    caps = [(support,loop[2]) for support,loop in zip(supports,loops)
            if len(loop)==3 and loop[2]>=n]
    if selected_caps and not caps:
        raise UnsupportedRoofError('no terminal triangular face for published gable adjustment')
    available_caps = {edge for edge,node in caps}
    if not selected_caps <= available_caps:
        raise UnsupportedRoofError('resolved gable end is not a supported terminal cap')
    caps = [(edge,node) for edge,node in caps if edge in selected_caps]
    cap_edges = {edge for edge,node in caps}
    locations = {i:BoundaryPoint(i,0.0) for i in range(n)}
    roles = ['corner' if i<n else 'junction' for i in range(len(seeds))]
    extensions = {}
    for edge,node in caps:
        a,b = fp.vertices[edge],fp.vertices[(edge+1)%n]
        # Replace the oriented triangular disk (a,b,node) with the two
        # adjacent slope sectors (a,k,node) and (k,b,node). Their common
        # k-node ridge retains the original event and every other incidence.
        # Across the cap edges the neighboring loops run node->b and a->node.
        k = len(seeds)
        t=cap_parameter(fp,edge)
        seeds.append(tuple((a[i]+b[i])/2 if t==.5 else a[i]+t*(b[i]-a[i]) for i in (0,1)))
        roles.append('ridge_end')
        locations[k] = BoundaryPoint(edge,t)
        for pair in ((node,(edge+1)%n),(edge,node)):
            owners = [loop for support,loop in zip(supports,loops)
                      if support not in cap_edges and
                      pair in tuple(zip(loop,loop[1:]+loop[:1]))]
            if len(owners)!=1 or pair in extensions:
                raise UnsupportedRoofError('terminal cap lacks two uniquely incident slope sectors')
            extensions[pair] = k
        # Opposed support normals make a terminal gable. Exact parallel lines
        # meet at the midpoint; bounded rounding uses their actual equality
        # locus. No support plane or footprint coordinate is rectified.
        if not opposed_supports(fp,edge):
            raise UnsupportedRoofError('terminal cap is not bounded by opposed slope supports')
    def extend(loop):
        result=[]
        for a,b in zip(loop,loop[1:]+loop[:1]):
            result.append(a)
            if (a,b) in extensions:result.append(extensions[a,b])
        return tuple(result)
    faces = [graph_api.RoofFace(extend(loop),(0,),(edge,),edge)
             for edge,loop in zip(supports,loops) if edge not in cap_edges]
    # Adjacent pieces with the same oriented supporting line describe one
    # roof facet. Remove only their common cycle edges; no metric seam repair.
    parent = list(range(len(faces)))
    def find(i):
        while parent[i]!=i:
            i=parent[i]
        return i
    def support_line(face):
        edge=face.support
        a,b=fp.vertices[edge],fp.vertices[(edge+1)%n]
        size=math.dist(a,b)
        normal=(-(b[1]-a[1])/size,(b[0]-a[0])/size)
        return normal, sum(x*y for x,y in zip(normal,a))
    shared=defaultdict(list)
    for i,face in enumerate(faces):
        for a,b in zip(face.loop,face.loop[1:]+face.loop[:1]):
            shared[tuple(sorted((a,b)))].append(i)
    lines=[support_line(face) for face in faces]
    for owners in shared.values():
        if len(owners)!=2:continue
        i,j=owners
        if (math.dist(lines[i][0],lines[j][0])<1e-8 and
            abs(lines[i][1]-lines[j][1])<1e-8):
            parent[find(j)]=find(i)
    groups=defaultdict(list)
    for i,face in enumerate(faces):groups[find(i)].append(face)
    merged=[]
    for group in groups.values():
        boundary=set()
        for face in group:
            for a,b in zip(face.loop,face.loop[1:]+face.loop[:1]):
                if (b,a) in boundary:boundary.remove((b,a))
                else:boundary.add((a,b))
        outgoing={a:b for a,b in boundary}
        if len(outgoing)!=len(boundary):
            raise UnsupportedRoofError('coplanar facet union has branching boundary')
        start=min(outgoing);loop=[];node=start
        while node not in loop:
            loop.append(node);node=outgoing[node]
        if node!=start or len(loop)!=len(boundary):
            raise UnsupportedRoofError('coplanar facet union is not one simple region')
        eaves=tuple(sorted({edge for face in group for edge in face.eaves}))
        merged.append(graph_api.RoofFace(tuple(loop),(0,),eaves,eaves[0]))
    faces=merged
    # Facet aggregation can leave a degree-two subdivision point on one
    # straight crease. Suppress that point in both incident cycles; keep
    # every boundary vertex and every actual junction.
    occurrences=defaultdict(list)
    for i,face in enumerate(faces):
        for j,node in enumerate(face.loop):
            occurrences[node].append((i,face.loop[j-1],face.loop[(j+1)%len(face.loop)]))
    redundant=set()
    for node,items in occurrences.items():
        if node in locations or len(items)!=2:continue
        (_,a,b),(_,c,d)=items
        if {a,b}!={c,d}:continue
        u=(seeds[a][0]-seeds[node][0],seeds[a][1]-seeds[node][1])
        v=(seeds[b][0]-seeds[node][0],seeds[b][1]-seeds[node][1])
        if abs(u[0]*v[1]-u[1]*v[0])<1e-10 and sum(x*y for x,y in zip(u,v))<0:
            redundant.add(node)
    faces=[graph_api.RoofFace(tuple(v for v in f.loop if v not in redundant),f.cells,f.eaves,f.support)
           for f in faces]
    incidence = defaultdict(list)
    for face_id,face in enumerate(faces):
        for a,b in zip(face.loop,face.loop[1:]+face.loop[:1]):
            incidence[tuple(sorted((a,b)))].append((face_id,a,b))
    normals = []
    for face in faces:
        edge = face.support
        a,b = fp.vertices[edge],fp.vertices[(edge+1)%n]
        size = math.dist(a,b)
        normals.append((-(b[1]-a[1])/size,(b[0]-a[0])/size))
    semantics = {}
    for key,owners in incidence.items():
        if len(owners)==1:
            a,b = key
            semantics[key] = 'gable_end' if roles[a]=='ridge_end' or roles[b]=='ridge_end' else 'eave'
            continue
        if len(owners)!=2:
            raise UnsupportedRoofError('skeleton has nonmanifold face incidence')
        (i,a,b),(j,_,_) = owners
        p,q = normals[i],normals[j]
        dot = sum(x*y for x,y in zip(p,q))
        if abs(dot+1)<1e-8:
            semantics[key] = 'ridge'
        else:
            # For an oriented face its left side is its interior. Source slope
            # normals determine convex/concave crease meaning before solving.
            dx,dy = seeds[b][0]-seeds[a][0],seeds[b][1]-seeds[a][1]
            sign = (q[0]-p[0])*(-dy)+(q[1]-p[1])*dx
            if abs(sign)<1e-12:
                raise UnsupportedRoofError('coplanar skeleton seam needs explicit face aggregation')
            semantics[key] = 'hip' if sign>0 else 'valley'
    used = sorted({v for face in faces for v in face.loop})
    remap = {old:new for new,old in enumerate(used)}
    faces = [graph_api.RoofFace(tuple(remap[v] for v in face.loop),face.cells,face.eaves,face.support)
             for face in faces]
    graph = graph_api.make_graph(fp.vertices,fp.source_edges,
        tuple(seeds[i] for i in used),{remap[i]:point for i,point in locations.items() if i in remap},
        tuple(roles[i] for i in used),faces,
        {tuple(sorted((remap[a],remap[b]))):kind for (a,b),kind in semantics.items()},structure.roof_type)
    return graph, {'cap_edges':sorted(cap_edges), 'skeleton_nodes':len(seeds),
                   'policy':'oriented terminal-cap disk replacement; preserve shared events; no appearance ranking'}
