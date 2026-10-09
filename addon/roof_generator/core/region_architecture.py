# SPDX-License-Identifier: GPL-3.0-or-later
"""Polygon support ownership and explicit rectangular gable model domains."""
from dataclasses import dataclass, asdict

from .architecture import Analysis, relation_options
from .architecture_models import ArchitecturalMember
from .errors import UnsupportedRoofError
from .footprint import EPS, area
from .member_layout import member_layout


@dataclass(frozen=True)
class RegionPart:
    id: int
    members: tuple[int,...]
    region: tuple[tuple[float,float],...]


@dataclass(frozen=True)
class RegionPartGraph:
    layout: object
    members: tuple[ArchitecturalMember,...]
    relations: tuple
    parts: tuple[RegionPart,...]

    def __post_init__(self):
        if tuple(m.cell for m in self.members)!=tuple(range(len(self.layout.supports))):
            raise UnsupportedRoofError('region models do not cover declared supports')
        assigned=sorted(m for p in self.parts for m in p.members)
        if assigned!=list(range(len(self.members))):
            raise UnsupportedRoofError('region parts do not cover model supports once')
        for model,region in zip(self.members,self.layout.candidate.regions):
            bounds=(min(p[0] for p in region.boundary),min(p[1] for p in region.boundary),
                    max(p[0] for p in region.boundary),max(p[1] for p in region.boundary))
            if any(abs(a-b)>4*EPS for a,b in zip(bounds,model.bounds)) or model.axes!=(0,1):
                raise UnsupportedRoofError('rectangular gable model changes polygon support/domain')

    @property
    def owners(self):
        return tuple(next(p.id for p in self.parts if m in p.members) for m in range(len(self.members)))

    def rebuild(self,analysis,*,compound_relations=None):
        return build_region_parts(self.layout,analysis,compound_relations=compound_relations)

    def inspect(self):
        return {'region_candidate':self.layout.candidate.inspect(),
                'members':[asdict(m) for m in self.members],
                'model_family':'rectangular_gable_declared_axis',
                'parts':[asdict(p) for p in self.parts],
                'relations':[asdict(r) for r in self.relations],'roof_topology':None}


def build_region_parts(layout,analysis,*,compound_relations=None):
    neighbors={s.id:set() for s in layout.supports}
    if compound_relations is not None:
        for a,b in compound_relations:
            neighbors[a].add(b);neighbors[b].add(a)
    remaining=set(neighbors)
    groups=[]
    while remaining:
        pending=[min(remaining)];group=set()
        while pending:
            member=pending.pop()
            if member not in group:
                group.add(member);pending.extend(neighbors[member]-group)
        groups.append(tuple(sorted(group)));remaining-=group
    parts=[]
    for group in sorted(groups):
        boundary=set()
        for member in group:
            ring=layout.supports[member].boundary
            for a,b in zip(ring,ring[1:]+ring[:1]):
                if (b,a) in boundary:boundary.remove((b,a))
                else:boundary.add((a,b))
        outgoing={a:b for a,b in boundary}
        if len(outgoing)!=len(boundary):
            raise UnsupportedRoofError('region part union is not a simple connected boundary')
        start=min(outgoing);ring=[];node=start
        while node not in ring:
            ring.append(node);node=outgoing[node]
        if node!=start or len(ring)!=len(boundary):
            raise UnsupportedRoofError('region part union has multiple boundary components')
        polygon=tuple(layout.vertices[i] for i in ring)
        if area(polygon)<=EPS**2:
            raise UnsupportedRoofError('region part has invalid oriented support')
        parts.append(RegionPart(len(parts),group,polygon))
    return RegionPartGraph(layout,analysis.members,analysis.relations,tuple(parts))


def interpret_regions(candidate):
    layout=member_layout(candidate)
    models=[]
    for support in layout.supports:
        points=tuple(layout.vertices[i] for i in support.corners)
        bounds=(min(p[0] for p in points),min(p[1] for p in points),
                max(p[0] for p in points),max(p[1] for p in points))
        # Direction belongs to the declared model, not a source Cell's long edge.
        # Both local template axes exist; global end and attachment constraints
        # decide which assignments have supported architecture and incidence.
        models.append(ArchitecturalMember(support.id,bounds,(0,1)))
    relations=relation_options(layout.vertices,layout.supports,
        tuple((a.members,a.sides,a.interval) for a in layout.adjacency),models)
    return build_region_parts(layout,Analysis(tuple(models),relations))
