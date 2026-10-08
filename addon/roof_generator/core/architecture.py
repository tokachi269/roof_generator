# SPDX-License-Identifier: GPL-3.0-or-later
"""Published end/side combinations and compound units, before roof topology."""

from collections import defaultdict
from dataclasses import dataclass, replace
from itertools import product
import math
from .footprint import EPS, area
from .architecture_models import (
    ArchitecturalMember,
    PartCombination,
    PartRelation,
    ArchitecturalPart,
    PartAdjacency,
    Issue,
    ArchitecturalPartGraph,
)
from .errors import UnsupportedRoofError, GenerationIssue


@dataclass(frozen=True)
class Analysis:
    members: tuple[ArchitecturalMember, ...]
    relations: tuple[PartRelation, ...]


@dataclass(frozen=True)
class ResolvedArchitecture:
    """Selected member directions and combinations; composition reads these."""

    architecture: ArchitecturalPartGraph
    axes: tuple[int, ...]
    relations: tuple[PartRelation, ...]

    def __post_init__(self):
        graph = self.architecture
        if len(self.axes) != len(graph.members) or any(
            axis not in member.axes for member, axis in zip(graph.members, self.axes)
        ):
            raise UnsupportedRoofError("resolved direction contradicts member domain")
        if len(self.relations) != len(graph.relations):
            raise UnsupportedRoofError("resolved architecture loses relations")
        for source, relation in zip(graph.relations, self.relations):
            assignment = tuple(self.axes[c] for c in source.cells)
            options = tuple(o for o in source.options if o.axes == assignment)
            if len(options) != 1 or relation != replace(source, options=options):
                raise UnsupportedRoofError("resolved architecture changes a combination")

    @property
    def decomposition(self):
        return self.architecture.decomposition

    @property
    def owners(self):
        return tuple(
            next(p.id for p in self.architecture.parts if m.cell in p.cells)
            for m in self.architecture.members
        )

    def internal(self, relation):
        owners = self.owners
        return owners[relation.cells[0]] == owners[relation.cells[1]]

    def analysis(self):
        return Analysis(
            tuple(replace(m, axes=(self.axes[m.cell],)) for m in self.architecture.members),
            self.relations,
        )


def resolve(architecture, axes):
    """Resolve ambiguity, without consulting implementation availability."""
    relations = []
    for relation in architecture.relations:
        assignment = tuple(axes[c] for c in relation.cells)
        options = tuple(o for o in relation.options if o.axes == assignment)
        if len(options) != 1:
            raise UnsupportedRoofError(
                "member axis assignment does not resolve a unique local relation",
                issues=(GenerationIssue("relation", "unresolved_relation", relation.cells),),
            )
        relations.append(replace(relation, options=options))
    return ResolvedArchitecture(architecture, tuple(axes), tuple(relations))


def analyze_parts(d):
    members = []
    for c in d.cells:
        pts = [d.vertices[i] for i in c.corners]
        b = (
            min(p[0] for p in pts),
            min(p[1] for p in pts),
            max(p[0] for p in pts),
            max(p[1] for p in pts),
        )
        sizes = (b[2] - b[0], b[3] - b[1])
        axes = (
            (0, 1)
            if abs(sizes[0] - sizes[1]) <= 4 * EPS
            else (int(sizes[1] > sizes[0]),)
        )
        if not d.footprint.orthogonal:
            edge = d.footprint.directions
            vectors = tuple(
                tuple(edge[i][k] - edge[(i + 2) % 4][k] for k in (0, 1)) for i in (0, 1)
            )
            directions = tuple(tuple(x / math.hypot(*v) for x in v) for v in vectors)
            members.append(ArchitecturalMember(c.id, b, (), directions))
        else:
            members.append(ArchitecturalMember(c.id, b, axes))
    shared = defaultdict(list)
    for a in d.adjacency:
        shared[(a.cells, a.sides)].append(a.interval)
    relations = []
    for (cells, sides), intervals in sorted(shared.items()):
        nodes = {v for edge in intervals for v in edge}
        ps = [d.vertices[v] for v in nodes]
        axis = int(max(p[1] for p in ps) - min(p[1] for p in ps) > EPS)
        lo, hi = min(p[axis] for p in ps), max(p[axis] for p in ps)
        full = []
        corner = []
        for c, s in zip(cells, sides):
            side = d.cells[c].sides[s]
            extent = sorted(d.vertices[v][axis] for v in side.vertices)
            full.append(
                abs(lo - extent[0]) <= 4 * EPS and abs(hi - extent[1]) <= 4 * EPS
            )
            corner.append(
                abs(lo - extent[0]) <= 4 * EPS or abs(hi - extent[1]) <= 4 * EPS
            )
        options = []
        for axes in product(*(members[c].axes for c in cells)):
            end = [a != axis for a in axes]
            if all(end):
                kind = "continuation"
                options.append(PartCombination(kind, axes))
            elif not any(end):
                options.append(PartCombination("parallel", axes))
            else:
                bi = end.index(True)
                hi_index = 1 - bi
                if not full[bi] or full[hi_index]:
                    options.append(PartCombination("partial_end", axes))
                    continue
                host, branch = cells[hi_index], cells[bi]
                hb, bb = members[host].bounds, members[branch].bounds
                widths = (hb[3 - axis] - hb[1 - axis], bb[2 + axis] - bb[axis])
                main = host if widths[0] > widths[1] + 4 * EPS else None
                kind = "corner" if corner[hi_index] else "side_attachment"
                options.append(PartCombination(kind, axes, host, branch, widths, main))
        relations.append(
            PartRelation(cells, sides, tuple(sorted(intervals)), tuple(options))
        )
    return Analysis(tuple(members), tuple(relations))


def _cycles(d, cells):
    """Cancel actual oriented cell edges; never replace coverage by a box."""
    boundary = set()
    for c in cells:
        ring = d.cells[c].boundary
        for a, b in zip(ring, ring[1:] + ring[:1]):
            if (b, a) in boundary:
                boundary.remove((b, a))
            else:
                boundary.add((a, b))
    outgoing = defaultdict(list)
    for a, b in boundary:
        outgoing[a].append(b)
    successor = {}
    for a, b in boundary:
        reverse = math.atan2(
            d.vertices[a][1] - d.vertices[b][1], d.vertices[a][0] - d.vertices[b][0]
        )
        c = min(
            outgoing[b],
            key=lambda c: (
                (
                    reverse
                    - math.atan2(
                        d.vertices[c][1] - d.vertices[b][1],
                        d.vertices[c][0] - d.vertices[b][0],
                    )
                )
                % (2 * math.pi),
                c,
            ),
        )
        successor[(a, b)] = (b, c)
    rings = []
    remaining = set(boundary)
    while remaining:
        first = min(remaining)
        edge = first
        ring = []
        while edge in remaining:
            remaining.remove(edge)
            ring.append(edge[0])
            edge = successor[edge]
        if edge != first:
            raise ValueError("compound boundary is not a cycle")
        rings.append(tuple(ring))
    return tuple(sorted(rings))


def build_parts(d, analysis):
    """Group all unambiguous corner/continuation components simultaneously.

    Compound units retain every rectangular member and every local combination.
    A compound boundary is not the footprint of an independent gable primitive.
    """
    neighbors = {c.id: set() for c in d.cells}
    issues = []
    for r in analysis.relations:
        kinds = {o.kind for o in r.options}
        if kinds <= {"corner", "continuation"}:
            a, b = r.cells
            neighbors[a].add(b)
            neighbors[b].add(a)
        if len(r.options) > 1:
            issues.append(
                Issue(
                    "axis_ambiguity",
                    r.cells,
                    "square member has multiple local axis/combination options",
                )
            )
        if kinds.intersection({"parallel", "partial_end"}):
            issues.append(
                Issue(
                    "unresolved_contact",
                    r.cells,
                    "parallel/partial-end contact needs an architectural choice; no roof is implied",
                )
            )
        if any(
            o.receiver is not None and o.widths[0] < o.widths[1] - 4 * EPS
            for o in r.options
        ):
            issues.append(
                Issue(
                    "width_roles",
                    r.cells,
                    "receiving member is narrower; narrow-to-wide extension cannot select this main",
                )
            )
    groups = []
    remaining = set(neighbors)
    while remaining:
        todo = [min(remaining)]
        group = set()
        while todo:
            c = todo.pop()
            if c in group:
                continue
            group.add(c)
            todo.extend(neighbors[c] - group)
        groups.append(tuple(sorted(group)))
        remaining -= group
    parts = []
    for i, cells in enumerate(sorted(groups)):
        rings = _cycles(d, cells)
        if len(rings) != 1 or any(
            len(set(r)) != len(r) or area(tuple(d.vertices[v] for v in r)) <= EPS**2
            for r in rings
        ):
            issues.append(
                Issue(
                    "compound_boundary",
                    cells,
                    "compound unit needs multiple or touching boundary cycles",
                )
            )
        exterior = tuple(
            sorted(
                (s for c in cells for side in d.cells[c].sides for s in side.exterior),
                key=lambda s: (s.edge, s.interval, s.original_edges),
            )
        )
        consumed = tuple(
            sorted(a.interval for a in d.adjacency if set(a.cells) <= set(cells))
        )
        axes = tuple(sorted({axis for c in cells for axis in analysis.members[c].axes}))
        parts.append(ArchitecturalPart(i, cells, rings, exterior, consumed, axes))
    owners = {c: p.id for p in parts for c in p.cells}
    adjacent = tuple(
        sorted(
            (
                PartAdjacency(
                    tuple(sorted(owners[c] for c in a.cells)), a.interval, a.cells
                )
                for a in d.adjacency
                if owners[a.cells[0]] != owners[a.cells[1]]
            ),
            key=lambda a: (a.parts, a.interval, a.cells),
        )
    )
    return ArchitecturalPartGraph(
        d,
        analysis.members,
        tuple(parts),
        analysis.relations,
        adjacent,
        tuple(sorted(issues, key=lambda i: (i.cells, i.code))),
    )


def interpret(d):
    return build_parts(d, analyze_parts(d))
