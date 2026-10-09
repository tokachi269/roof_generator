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
            if (any(abs(a-b)>4*EPS for a,b in zip(bounds,model.bounds))
                or not model.axes or any(a not in (0,1) for a in model.axes)):
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


def interpret_receiver(candidate):
    """Declared receiver/leaf family; no area priority or guessed ridge axis."""
    from dataclasses import replace
    architecture=interpret_regions(candidate)
    n=len(architecture.members)
    neighbors={i:set() for i in range(n)}
    directions={}
    for contact in architecture.layout.adjacency:
        a,b=contact.members
        neighbors[a].add(b);neighbors[b].add(a)
        points=[architecture.layout.vertices[v] for v in contact.interval]
        directions[a,b]=int(abs(points[1][1]-points[0][1])>EPS)
    domains=[set() for _ in range(n)]
    for root in range(n):
        if len(neighbors[root])!=n-1 or any(len(neighbors[i])!=1 for i in range(n) if i!=root):continue
        bounds=architecture.members[root].bounds
        lengths=(bounds[2]-bounds[0],bounds[3]-bounds[1])
        for axis in (0,1):
            if lengths[axis]+4*EPS<lengths[1-axis]:continue
            if any(direction!=axis for pair,direction in directions.items() if root in pair):continue
            domains[root].add(axis)
            for leaf in range(n):
                if leaf!=root:domains[leaf].add(1-axis)
    if any(not domain for domain in domains):
        raise UnsupportedRoofError('no long-axis receiver with perpendicular exterior leaves')
    members=tuple(replace(m,axes=tuple(sorted(domain))) for m,domain in zip(architecture.members,domains))
    relations=relation_options(architecture.layout.vertices,architecture.layout.supports,
        tuple((a.members,a.sides,a.interval) for a in architecture.layout.adjacency),members)
    return build_region_parts(architecture.layout,Analysis(members,relations))
