# SPDX-License-Identifier: GPL-3.0-or-later
"""Architectural interpretation contract. No roof faces, features or heights."""

from dataclasses import dataclass, asdict
from .provenance import BoundarySpan
from .errors import UnsupportedRoofError
from .cells import Decomposition
from .footprint import EPS


@dataclass(frozen=True)
class ArchitecturalMember:
    cell: int
    bounds: tuple[float, float, float, float]
    axes: tuple[int, ...]
    directions: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class PartCombination:
    kind: str
    axes: tuple[int, int]
    receiver: int | None = None
    branch: int | None = None
    widths: tuple[float, float] = ()  # receiver, branch transverse dimensions
    main: int | None = None  # strictly wider local member, never a global ranking


@dataclass(frozen=True)
class PartRelation:
    cells: tuple[int, int]
    sides: tuple[int, int]
    intervals: tuple[tuple[int, int], ...]
    options: tuple[PartCombination, ...]


@dataclass(frozen=True)
class ArchitecturalPart:
    id: int
    cells: tuple[int, ...]
    boundaries: tuple[tuple[int, ...], ...]
    exterior: tuple[BoundarySpan, ...]
    consumed: tuple[tuple[int, int], ...]
    axes: tuple[int, ...]


@dataclass(frozen=True)
class PartAdjacency:
    parts: tuple[int, int]
    interval: tuple[int, int]
    cells: tuple[int, int]


@dataclass(frozen=True)
class Issue:
    code: str
    cells: tuple[int, ...]
    message: str


@dataclass(frozen=True)
class ArchitecturalPartGraph:
    decomposition: Decomposition
    members: tuple[ArchitecturalMember, ...]
    parts: tuple[ArchitecturalPart, ...]
    relations: tuple[PartRelation, ...]
    adjacency: tuple[PartAdjacency, ...]
    issues: tuple[Issue, ...]

    def __post_init__(self):
        d = self.decomposition
        assigned = [c for p in self.parts for c in p.cells]
        if sorted(assigned) != list(range(len(d.cells))):
            raise UnsupportedRoofError(
                "part membership must cover every cell exactly once"
            )
        if tuple(p.id for p in self.parts) != tuple(range(len(self.parts))):
            raise UnsupportedRoofError("part IDs must be ordered and dense")
        if tuple(m.cell for m in self.members) != tuple(range(len(d.cells))):
            raise UnsupportedRoofError("architectural members must cover every cell")
        for m in self.members:
            pts = [d.vertices[v] for v in d.cells[m.cell].corners]
            bounds = (
                min(p[0] for p in pts),
                min(p[1] for p in pts),
                max(p[0] for p in pts),
                max(p[1] for p in pts),
            )
            if any(abs(a - b) > 4 * EPS for a, b in zip(m.bounds, bounds)):
                raise UnsupportedRoofError("member bounds differ from its cell")
            sizes = bounds[2] - bounds[0], bounds[3] - bounds[1]
            axes = (
                (0, 1)
                if abs(sizes[0] - sizes[1]) <= 4 * EPS
                else (int(sizes[1] > sizes[0]),)
            )
            if not d.footprint.orthogonal:
                import math
                from .footprint import sub

                directions = tuple(sub(pts[(i + 1) % 4], pts[i]) for i in range(4))
                units = tuple(tuple(x / math.hypot(*v) for x in v) for v in directions)
                vectors = tuple(
                    tuple(units[i][k] - units[(i + 2) % 4][k] for k in (0, 1))
                    for i in (0, 1)
                )
                expected = tuple(tuple(x / math.hypot(*v) for x in v) for v in vectors)
                if m.axes or m.directions != expected:
                    raise UnsupportedRoofError(
                        "quadrilateral member requires geometric directions, not orthogonal axes"
                    )
            elif m.axes != axes:
                raise UnsupportedRoofError(
                    "member axes differ from its geometric domain"
                )
        owners = {c: p.id for p in self.parts for c in p.cells}
        for p in self.parts:
            boundary = set()
            for c in p.cells:
                ring = d.cells[c].boundary
                for a, b in zip(ring, ring[1:] + ring[:1]):
                    if (b, a) in boundary:
                        boundary.remove((b, a))
                    else:
                        boundary.add((a, b))
            actual = [
                (a, b)
                for ring in p.boundaries
                for a, b in zip(ring, ring[1:] + ring[:1])
            ]
            if len(set(actual)) != len(actual) or set(actual) != boundary:
                raise UnsupportedRoofError(
                    "part exterior differs from canceled cell boundaries"
                )
            expected = {a.interval for a in d.adjacency if set(a.cells) <= set(p.cells)}
            if set(p.consumed) != expected or len(p.consumed) != len(expected):
                raise UnsupportedRoofError(
                    "part consumed cuts differ from internal adjacency"
                )
            spans = [
                s for c in p.cells for side in d.cells[c].sides for s in side.exterior
            ]
            key = lambda s: (s.edge, s.interval, s.original_edges)
            if sorted(p.exterior, key=key) != sorted(spans, key=key):
                raise UnsupportedRoofError("part lost exterior provenance")
        expected = {
            PartAdjacency(
                tuple(sorted(owners[c] for c in a.cells)), a.interval, a.cells
            )
            for a in d.adjacency
            if owners[a.cells[0]] != owners[a.cells[1]]
        }
        if set(self.adjacency) != expected or len(self.adjacency) != len(expected):
            raise UnsupportedRoofError("part adjacency differs from retained cuts")
        pairs = {a.cells for a in d.adjacency}
        if {r.cells for r in self.relations} != pairs:
            raise UnsupportedRoofError("part relations lost cell adjacency")
        for r in self.relations:
            expected = {
                a.interval
                for a in d.adjacency
                if a.cells == r.cells and a.sides == r.sides
            }
            if set(r.intervals) != expected or len(r.intervals) != len(expected):
                raise UnsupportedRoofError("relation lost shared interval provenance")
            if not r.options:
                raise UnsupportedRoofError(
                    "unresolved contact needs an explicit option"
                )
            for o in r.options:
                if any(
                    axis not in self.members[c].axes for c, axis in zip(r.cells, o.axes)
                ):
                    raise UnsupportedRoofError(
                        "relation axis contradicts member domain"
                    )
                if o.receiver is not None and {o.receiver, o.branch} != set(r.cells):
                    raise UnsupportedRoofError(
                        "attachment roles contradict incident cells"
                    )
                if o.main is not None and o.main not in r.cells:
                    raise UnsupportedRoofError("local main is not an incident member")
                if o.main is not None and (
                    o.main != o.receiver
                    or len(o.widths) != 2
                    or o.widths[0] <= o.widths[1] + 4 * EPS
                ):
                    raise UnsupportedRoofError(
                        "local main lacks a strict receiving-width justification"
                    )

    def inspect(self):
        return {
            "members": [asdict(m) for m in self.members],
            "parts": [asdict(p) for p in self.parts],
            "relations": [asdict(r) for r in self.relations],
            "adjacency": [asdict(a) for a in self.adjacency],
            "issues": [asdict(i) for i in self.issues],
            "roof_topology": None,
        }
