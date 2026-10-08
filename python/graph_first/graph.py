# SPDX-License-Identifier: GPL-3.0-or-later
"""Indexed topology, explicit semantics and boundary ownership, without planes."""

from dataclasses import dataclass
from collections import Counter, defaultdict
import math

Point = tuple[float, float]
KINDS = frozenset(("ridge", "hip", "valley", "eave", "gable_end"))


class UnsupportedGraphError(ValueError):
    """No graph in the explicitly supported composition scope exists."""


@dataclass(frozen=True)
class BoundaryPoint:
    edge: int
    t: float


@dataclass(frozen=True)
class Vertex:
    seed: Point
    role: str
    boundary: BoundaryPoint | None
    cells: tuple[int, ...]


@dataclass(frozen=True)
class Face:
    loop: tuple[int, ...]
    cells: tuple[int, ...]
    eaves: tuple[int, ...]


@dataclass(frozen=True)
class BoundarySpan:
    edge: int
    interval: tuple[float, float]
    original_edges: tuple[int, ...]


@dataclass(frozen=True)
class Edge:
    vertices: tuple[int, int]
    faces: tuple[int, ...]
    kind: str
    boundary: BoundarySpan | None


@dataclass(frozen=True)
class RoofGraph:
    outline: tuple[Point, ...]
    source_edges: tuple[tuple[int, ...], ...]
    vertices: tuple[Vertex, ...]
    faces: tuple[Face, ...]
    edges: tuple[Edge, ...]
    roof_type: str

    def __post_init__(self):
        n = len(self.vertices)
        if len(self.outline) < 3 or len(self.source_edges) != len(self.outline):
            raise UnsupportedGraphError("invalid outline/provenance contract")
        if not self.faces or any(
            len(f.loop) < 3
            or len(set(f.loop)) != len(f.loop)
            or any(i < 0 or i >= n for i in f.loop)
            or not f.cells
            for f in self.faces
        ):
            raise UnsupportedGraphError("invalid face cycle/index/cell ownership")
        canonical = [
            min(f.loop[i:] + f.loop[:i] for i in range(len(f.loop))) for f in self.faces
        ]
        if len(set(canonical)) != len(canonical):
            raise UnsupportedGraphError("duplicate face cycle")
        incidence = defaultdict(list)
        owners = defaultdict(set)
        for i, f in enumerate(self.faces):
            for v in f.loop:
                owners[v].update(f.cells)
            for a, b in zip(f.loop, f.loop[1:] + f.loop[:1]):
                incidence[tuple(sorted((a, b)))].append((i, a, b))
        if set(owners) != set(range(n)):
            raise UnsupportedGraphError("unused graph vertex")
        if len(self.edges) != len(incidence) or len(
            {e.vertices for e in self.edges}
        ) != len(self.edges):
            raise UnsupportedGraphError("missing or duplicated graph edge")
        perimeter, adjacency = defaultdict(set), defaultdict(set)
        coverage = defaultdict(list)
        for edge in self.edges:
            items = incidence.get(edge.vertices, ())
            if len(items) not in (1, 2) or edge.faces != tuple(i for i, _, _ in items):
                raise UnsupportedGraphError("edge/face incidence mismatch")
            if edge.kind not in KINDS:
                raise UnsupportedGraphError("undeclared roof edge semantics")
            if len(items) == 2:
                (i, a, b), (j, c, d) = items
                if (
                    (a, b) != (d, c)
                    or edge.boundary is not None
                    or edge.kind in {"eave", "gable_end"}
                ):
                    raise UnsupportedGraphError("invalid oriented interior edge")
                adjacency[i].add(j)
                adjacency[j].add(i)
            else:
                a, b = edge.vertices
                if edge.boundary is None or edge.kind not in {"eave", "gable_end"}:
                    raise UnsupportedGraphError("perimeter lacks boundary ownership")
                span = edge.boundary
                if (
                    not 0 <= span.edge < len(self.outline)
                    or span.original_edges != self.source_edges[span.edge]
                ):
                    raise UnsupportedGraphError("invalid exterior-edge provenance")
                lo, hi = span.interval
                if not 0 <= lo < hi <= 1:
                    raise UnsupportedGraphError("invalid boundary interval")
                coverage[span.edge].append((lo, hi))
                perimeter[a].add(b)
                perimeter[b].add(a)
        for i in range(len(self.outline)):
            spans = sorted(coverage[i])
            last = 0.0
            for lo, hi in spans:
                if abs(lo - last) > 1e-9:
                    raise UnsupportedGraphError("exterior boundary gap/overlap")
                last = hi
            if abs(last - 1) > 1e-9:
                raise UnsupportedGraphError("unowned exterior boundary")
        if any(len(v) != 2 for v in perimeter.values()) or not _connected(perimeter):
            raise UnsupportedGraphError("graph boundary is not one cycle")
        if len(self.faces) > 1 and not _connected(adjacency):
            raise UnsupportedGraphError("disconnected roof faces")
        if n - len(self.edges) + len(self.faces) != 1:
            raise UnsupportedGraphError("roof graph is not a disk")
        for i, vertex in enumerate(self.vertices):
            if vertex.cells != tuple(sorted(owners[i])) or not all(
                math.isfinite(v) for v in vertex.seed
            ):
                raise UnsupportedGraphError("invalid vertex seed/cell provenance")
            if (i in perimeter) != (vertex.boundary is not None):
                raise UnsupportedGraphError("boundary vertex ownership mismatch")
            if vertex.boundary is not None:
                p = vertex.boundary
                if (
                    not 0 <= p.edge < len(self.outline)
                    or not math.isfinite(p.t)
                    or not 0 <= p.t < 1
                ):
                    raise UnsupportedGraphError("invalid fixed boundary point")
                a, b = (
                    self.outline[p.edge],
                    self.outline[(p.edge + 1) % len(self.outline)],
                )
                expected = tuple(a[k] + p.t * (b[k] - a[k]) for k in (0, 1))
                if math.dist(vertex.seed, expected) > 2e-8:
                    raise UnsupportedGraphError(
                        "seed violates fixed footprint boundary"
                    )
            link = defaultdict(set)
            for face in self.faces:
                if i in face.loop:
                    j = face.loop.index(i)
                    a, b = face.loop[j - 1], face.loop[(j + 1) % len(face.loop)]
                    link[a].add(b)
                    link[b].add(a)
            degrees = [len(adjacent) for adjacent in link.values()]
            if (
                not _connected(link)
                or any(d not in (1, 2) for d in degrees)
                or degrees.count(1) != (2 if i in perimeter else 0)
            ):
                raise UnsupportedGraphError("nonmanifold vertex link")

    def inspect(self):
        """Read the authoritative graph; do not derive semantics from geometry."""
        from dataclasses import asdict

        degrees = Counter(v for e in self.edges for v in e.vertices)
        return {
            "roof_type": self.roof_type,
            "outline": self.outline,
            "source_edges": self.source_edges,
            "vertices": [
                dict(asdict(v), id=i, degree=degrees[i])
                for i, v in enumerate(self.vertices)
            ],
            "faces": [dict(asdict(f), id=i) for i, f in enumerate(self.faces)],
            "edges": [asdict(e) for e in self.edges],
            "features": dict(Counter(e.kind for e in self.edges)),
            "face_adjacency": [e.faces for e in self.edges if len(e.faces) == 2],
        }


def _connected(graph):
    if not graph:
        return False
    seen, pending = set(), [next(iter(graph))]
    while pending:
        v = pending.pop()
        if v not in seen:
            seen.add(v)
            pending.extend(graph[v] - seen)
    return seen == set(graph)


def make_graph(
    outline, source_edges, seeds, locations, roles, faces, semantics, roof_type
):
    """Assemble incidence once from selected cycles and explicit edge meanings."""
    incidence, cells = defaultdict(list), defaultdict(set)
    for i, face in enumerate(faces):
        for v in face.loop:
            cells[v].update(face.cells)
        for a, b in zip(face.loop, face.loop[1:] + face.loop[:1]):
            incidence[tuple(sorted((a, b)))].append(i)
    if set(semantics) != set(incidence):
        raise UnsupportedGraphError("every selected graph edge needs one meaning")
    edges = []
    for (a, b), owners in sorted(incidence.items()):
        span = None
        if len(owners) == 1:
            first, second = locations.get(a), locations.get(b)
            if first is None or second is None:
                raise UnsupportedGraphError("perimeter vertex has no boundary location")
            span = boundary_span(outline, source_edges, first, second)
        edges.append(Edge((a, b), tuple(owners), semantics[a, b], span))
    vertices = tuple(
        Vertex(tuple(p), roles[i], locations.get(i), tuple(sorted(cells[i])))
        for i, p in enumerate(seeds)
    )
    return RoofGraph(
        tuple(outline),
        tuple(source_edges),
        vertices,
        tuple(faces),
        tuple(edges),
        roof_type,
    )


def boundary_span(outline, source_edges, first, second):
    """Resolve declared boundary locations, never infer from roof geometry."""
    candidates = []
    for edge in range(len(outline)):
        values = []
        for p in (first, second):
            if p.edge == edge:
                values.append(p.t)
            elif p.edge == (edge + 1) % len(outline) and p.t == 0:
                values.append(1.0)
        if len(values) == 2 and values[0] != values[1]:
            candidates.append(
                BoundarySpan(edge, tuple(sorted(values)), source_edges[edge])
            )
    if len(candidates) != 1:
        raise UnsupportedGraphError("ambiguous boundary segment ownership")
    return candidates[0]
