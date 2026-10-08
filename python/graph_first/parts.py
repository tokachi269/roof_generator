# SPDX-License-Identifier: GPL-3.0-or-later
"""Architectural interpretation contract. No roof faces, features or heights."""

from dataclasses import dataclass, asdict
from .graph import BoundarySpan, UnsupportedGraphError
from .cells import Decomposition


@dataclass(frozen=True)
class Member:
    cell: int
    bounds: tuple[float, float, float, float]
    axes: tuple[int, ...]


@dataclass(frozen=True)
class Combination:
    kind: str
    axes: tuple[int, int]
    receiver: int | None = None
    branch: int | None = None
    widths: tuple[float, float] = ()  # receiver, branch transverse dimensions
    main: int | None = None  # strictly wider local member, never a global ranking


@dataclass(frozen=True)
class Relation:
    cells: tuple[int, int]
    sides: tuple[int, int]
    intervals: tuple[tuple[int, int], ...]
    options: tuple[Combination, ...]


@dataclass(frozen=True)
class Part:
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
    members: tuple[Member, ...]
    parts: tuple[Part, ...]
    relations: tuple[Relation, ...]
    adjacency: tuple[PartAdjacency, ...]
    issues: tuple[Issue, ...]

    def __post_init__(self):
        d = self.decomposition
        assigned = [c for p in self.parts for c in p.cells]
        if sorted(assigned) != list(range(len(d.cells))):
            raise UnsupportedGraphError(
                "part membership must cover every cell exactly once"
            )
        if tuple(p.id for p in self.parts) != tuple(range(len(self.parts))):
            raise UnsupportedGraphError("part IDs must be ordered and dense")
        if tuple(m.cell for m in self.members) != tuple(range(len(d.cells))):
            raise UnsupportedGraphError("architectural members must cover every cell")
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
                raise UnsupportedGraphError(
                    "part exterior differs from canceled cell boundaries"
                )
            expected = {a.interval for a in d.adjacency if set(a.cells) <= set(p.cells)}
            if set(p.consumed) != expected or len(p.consumed) != len(expected):
                raise UnsupportedGraphError(
                    "part consumed cuts differ from internal adjacency"
                )
            spans = [
                s for c in p.cells for side in d.cells[c].sides for s in side.exterior
            ]
            key = lambda s: (s.edge, s.interval, s.original_edges)
            if sorted(p.exterior, key=key) != sorted(spans, key=key):
                raise UnsupportedGraphError("part lost exterior provenance")
        expected = {
            PartAdjacency(
                tuple(sorted(owners[c] for c in a.cells)), a.interval, a.cells
            )
            for a in d.adjacency
            if owners[a.cells[0]] != owners[a.cells[1]]
        }
        if set(self.adjacency) != expected or len(self.adjacency) != len(expected):
            raise UnsupportedGraphError("part adjacency differs from retained cuts")
        pairs = {a.cells for a in d.adjacency}
        if {r.cells for r in self.relations} != pairs:
            raise UnsupportedGraphError("part relations lost cell adjacency")
        for r in self.relations:
            if not r.options:
                raise UnsupportedGraphError(
                    "unresolved contact needs an explicit option"
                )
            for o in r.options:
                if any(
                    axis not in self.members[c].axes for c, axis in zip(r.cells, o.axes)
                ):
                    raise UnsupportedGraphError(
                        "relation axis contradicts member domain"
                    )
                if o.receiver is not None and {o.receiver, o.branch} != set(r.cells):
                    raise UnsupportedGraphError(
                        "attachment roles contradict incident cells"
                    )
                if o.main is not None and o.main not in r.cells:
                    raise UnsupportedGraphError("local main is not an incident member")

    def inspect(self):
        return {
            "members": [asdict(m) for m in self.members],
            "parts": [asdict(p) for p in self.parts],
            "relations": [asdict(r) for r in self.relations],
            "adjacency": [asdict(a) for a in self.adjacency],
            "issues": [asdict(i) for i in self.issues],
            "roof_topology": None,
        }
