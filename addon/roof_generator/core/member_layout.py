# SPDX-License-Identifier: GPL-3.0-or-later
"""Indexed support geometry from accepted polygon regions; no minimum Cells."""
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
import math

from .errors import UnsupportedRoofError
from .footprint import EPS, on_segment, rectangle, sub
from .provenance import BoundarySpan
from .roof_regions import RoofRegionCandidate, minimum_regions


@dataclass(frozen=True)
class MemberSide:
    vertices: tuple[int,int]
    exterior: tuple[BoundarySpan,...]
    interior: tuple[tuple[int,int],...]


@dataclass(frozen=True)
class MemberSupport:
    id: int
    corners: tuple[int,...]
    boundary: tuple[int,...]
    sides: tuple[MemberSide,...]


@dataclass(frozen=True)
class SupportContact:
    members: tuple[int,int]
    sides: tuple[int,int]
    interval: tuple[int,int]


@dataclass(frozen=True)
class MemberLayout:
    candidate: RoofRegionCandidate
    vertices: tuple[tuple[float,float],...]
    supports: tuple[MemberSupport,...]
    adjacency: tuple[SupportContact,...]

    @property
    def footprint(self):
        return self.candidate.footprint


@lru_cache(maxsize=64)
def minimum_layout(decomposition):
    """Publish the minimum source's indexed supports without changing its IDs.

    This producer preserves existing source indexing for declared relations.
    The shared composer receives MemberSupport records, not minimum Cells.
    Immutable source geometry is shared across axis/end hypotheses. The cache
    is bounded; it does not cache architecture decisions or seed selections.
    """
    candidate=minimum_regions(decomposition)
    supports=tuple(MemberSupport(c.id,c.corners,c.boundary,
                   tuple(MemberSide(s.vertices,s.exterior,s.artificial) for s in c.sides))
                   for c in decomposition.cells)
    contacts=tuple(SupportContact(a.cells,a.sides,a.interval) for a in decomposition.adjacency)
    return MemberLayout(candidate,decomposition.vertices,supports,contacts)


def member_layout(candidate):
    """Node accepted rectangular model supports for declared junction ports.

    Every member remains its actual region. Noding contact/exterior segments
    does not create smaller semantic members or infer any roof operation.
    Nonrectangular roof models remain unsupported at this model boundary.
    """
    if not isinstance(candidate,RoofRegionCandidate):
        raise TypeError('member layout requires polygon region authority')
    fp=candidate.footprint
    nodes=list(fp.vertices)
    def index(point):
        found=next((i for i,p in enumerate(nodes) if math.dist(point,p)<=4*EPS),None)
        if found is None:
            nodes.append(point)
            return len(nodes)-1
        return found
    corners=[]
    for region in candidate.regions:
        if len(region.boundary)!=4 or not rectangle(region.boundary):
            raise UnsupportedRoofError('nonrectangular region needs an explicit roof model')
        corners.append(tuple(index(p) for p in region.boundary))
    intervals=defaultdict(list)
    pieces={}
    for member,ring in enumerate(corners):
        for side,(a,b) in enumerate(zip(ring,ring[1:]+ring[:1])):
            pa,pb=nodes[a],nodes[b]
            direction=sub(pb,pa)
            order=sorted((i for i,p in enumerate(nodes) if on_segment(p,pa,pb)),
                         key=lambda i:sum(x*y for x,y in zip(sub(nodes[i],pa),direction)))
            pieces[member,side]=tuple(zip(order,order[1:]))
            for u,v in pieces[member,side]:
                if u!=v:
                    intervals[tuple(sorted((u,v)))].append((member,side,u,v))
    spans={}
    adjacent=[]
    for edge,owners in intervals.items():
        if len(owners)==2:
            first,second=sorted(owners)
            if first[2:]!=tuple(reversed(second[2:])):
                raise UnsupportedRoofError('member contact does not have opposite boundary incidence')
            adjacent.append(SupportContact((first[0],second[0]),(first[1],second[1]),edge))
        elif len(owners)==1:
            u,v=edge
            original=next((i for i,(a,b) in enumerate(zip(fp.vertices,fp.vertices[1:]+fp.vertices[:1]))
                           if on_segment(nodes[u],a,b) and on_segment(nodes[v],a,b)),None)
            if original is None:
                raise UnsupportedRoofError('member boundary has an unowned interior interval')
            a=fp.vertices[original]
            vector=sub(fp.vertices[(original+1)%len(fp.vertices)],a)
            size=sum(x*x for x in vector)
            values=sorted(sum(x*y for x,y in zip(sub(nodes[i],a),vector))/size for i in edge)
            spans[edge]=BoundarySpan(original,(max(0.,values[0]),min(1.,values[1])),fp.source_edges[original])
        else:
            raise UnsupportedRoofError('member interval has invalid ownership')
    supports=[]
    for member,ring in enumerate(corners):
        sides=[]
        boundary=[]
        for side,(a,b) in enumerate(zip(ring,ring[1:]+ring[:1])):
            segments=pieces[member,side]
            boundary.extend(u for u,v in segments)
            keys=tuple(tuple(sorted(e)) for e in segments)
            sides.append(MemberSide((a,b),tuple(spans[e] for e in keys if e in spans),
                                    tuple(e for e in keys if e not in spans)))
        supports.append(MemberSupport(member,ring,tuple(boundary),tuple(sides)))
    return MemberLayout(candidate,tuple(nodes),tuple(supports),tuple(sorted(adjacent,key=lambda a:(a.members,a.sides,a.interval))))
