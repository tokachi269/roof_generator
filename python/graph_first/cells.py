# SPDX-License-Identifier: GPL-3.0-or-later
"""Single-reflex rectangle partition by two visible extension chords.

No recursive polygon splitting, roof candidates or general minimum-part claim.
"""

from dataclasses import dataclass, asdict
import math
from .footprint import EPS, sub, cross, on_segment, rectangle, ray_hit, area
from .graph import BoundarySpan, UnsupportedGraphError
from .rectangle_partition import partition, Subdivision, PartitionCertificate, corners


@dataclass(frozen=True)
class Side:
    vertices: tuple[int, int]
    exterior: tuple[BoundarySpan, ...]
    artificial: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Cell:
    id: int
    corners: tuple[int, ...]
    boundary: tuple[int, ...]
    sides: tuple[Side, ...]


@dataclass(frozen=True)
class Adjacency:
    cells: tuple[int, int]
    sides: tuple[int, int]
    interval: tuple[int, int]


@dataclass(frozen=True)
class Decomposition:
    footprint: object
    vertices: tuple[tuple[float, float], ...]
    cells: tuple[Cell, ...]
    adjacency: tuple[Adjacency, ...]
    candidates: int
    certificate: PartitionCertificate | None = None

    def inspect(self):
        return {
            "vertices": self.vertices,
            "cells": [asdict(c) for c in self.cells],
            "adjacency": [asdict(a) for a in self.adjacency],
            "candidates": self.candidates,
            "certificate": asdict(self.certificate) if self.certificate else None,
        }


def _corners(boundary, nodes):
    ring = list(boundary)
    while len(ring) > 3:
        for i, v in enumerate(ring):
            a, b = sub(nodes[v], nodes[ring[i - 1]]), sub(
                nodes[ring[(i + 1) % len(ring)]], nodes[v]
            )
            if (
                abs(cross(a, b)) <= EPS * math.hypot(*a)
                and sum(x * y for x, y in zip(a, b)) >= 0
            ):
                ring.pop(i)
                break
        else:
            break
    return tuple(ring)


def _signature(ring, nodes):
    points = tuple(tuple(round(x, 10) for x in nodes[i]) for i in ring)
    return min(points[i:] + points[:i] for i in range(len(points)))


def _spans(a, b, footprint):
    result = []
    for i, c in enumerate(footprint.vertices):
        d = footprint.vertices[(i + 1) % len(footprint.vertices)]
        edge = sub(d, c)
        size = math.hypot(*edge)
        if (
            abs(cross(edge, sub(a, c))) > EPS * size
            or abs(cross(edge, sub(b, c))) > EPS * size
        ):
            continue
        values = [sum(x * y for x, y in zip(sub(p, c), edge)) / size**2 for p in (a, b)]
        lo, hi = max(0.0, min(values)), min(1.0, max(values))
        if (hi - lo) * size > EPS:
            result.append(BoundarySpan(i, (lo, hi), footprint.source_edges[i]))
    return tuple(result)


def _assemble(fp, nodes, rings, cut, candidates):
    rings = tuple(
        sorted(rings, key=lambda ring: _signature(_corners(ring, nodes), nodes))
    )
    cells = []
    shared = []
    for ci, ring in enumerate(rings):
        corners = _corners(ring, nodes)
        sides = []
        for si, (a, b) in enumerate(zip(corners, corners[1:] + corners[:1])):
            artificial = ()
            if cut is not None and all(
                on_segment(nodes[i], nodes[a], nodes[b]) for i in cut
            ):
                artificial = (cut,)
                shared.append((ci, si))
            sides.append(Side((a, b), _spans(nodes[a], nodes[b], fp), artificial))
        cells.append(Cell(ci, corners, tuple(ring), tuple(sides)))
    adjacency = ()
    if cut is not None:
        if len(shared) != 2:
            raise UnsupportedGraphError("cut does not belong to exactly two cell sides")
        adjacency = (
            Adjacency((shared[0][0], shared[1][0]), (shared[0][1], shared[1][1]), cut),
        )
    if (
        abs(
            sum(area(tuple(nodes[i] for i in c.boundary)) for c in cells)
            - area(fp.vertices)
        )
        > EPS
    ):
        raise UnsupportedGraphError("cell partition violates outline area")
    return Decomposition(fp, tuple(nodes), tuple(cells), adjacency, candidates)


def decompose(fp):
    if not fp.orthogonal:
        raise UnsupportedGraphError(
            "evaluation decomposition requires an orthogonal outline in its own frame"
        )
    if rectangle(fp.vertices):
        return _assemble(fp, fp.vertices, (tuple(range(4)),), None, 0)
    if len(fp.reflex) != 1:
        raise UnsupportedGraphError(
            "evaluation partition supports exactly one reflex vertex"
        )
    start = fp.reflex[0]
    candidates = []
    # Standard reflex-edge extensions. A rectangle cannot contain this reflex;
    # a valid two-rectangle partition is therefore minimum for this scope.
    directions = (fp.directions[start - 1], tuple(-v for v in fp.directions[start]))
    for direction in directions:
        hit = ray_hit(fp.vertices, start, direction)
        if hit is None:
            continue
        point, edge = hit
        nodes = list(fp.vertices)
        end = next(
            (i for i, p in enumerate(nodes) if math.dist(p, point) <= EPS), len(nodes)
        )
        if end == len(nodes):
            nodes.append(point)
        walk = tuple((start + i) % len(fp.vertices) for i in range(len(fp.vertices)))
        k = (edge - start) % len(fp.vertices)
        rings = (walk[: k + 1] + (end,), (end,) + walk[k + 1 :] + (start,))
        rings = tuple(
            tuple(v for i, v in enumerate(ring) if v != ring[i - 1]) for ring in rings
        )
        corners = tuple(_corners(ring, nodes) for ring in rings)
        if not all(rectangle(tuple(nodes[i] for i in ring)) for ring in corners):
            continue
        aspects = []
        for ring in corners:
            lengths = [
                math.dist(nodes[a], nodes[b]) for a, b in zip(ring, ring[1:] + ring[:1])
            ]
            aspects.append(max(lengths) / min(lengths))
        cost = (
            tuple(sorted((round(v, 8) for v in aspects), reverse=True)),
            round(math.dist(nodes[start], nodes[end]), 10),
            tuple(sorted(tuple(round(x, 10) for x in nodes[i]) for i in (start, end))),
        )
        candidates.append((cost, tuple(nodes), rings, (start, end)))
    if not candidates:
        raise UnsupportedGraphError(
            "no visible reflex chord gives two rectangular cells"
        )
    _, nodes, rings, cut = min(candidates, key=lambda c: c[0])
    return _assemble(fp, nodes, rings, cut, len(candidates))


# This generic entry is proved alongside the prototype before replacing it.
def minimum_decompose(fp):
    return from_subdivision(fp, partition(fp))


def from_subdivision(fp, subdivision: Subdivision):
    """Convert a noded rectangular subdivision to roof-independent cell records."""
    nodes = subdivision.vertices
    rings = tuple(
        sorted(subdivision.faces, key=lambda f: _signature(corners(f, nodes), nodes))
    )
    exterior = {e.vertices: e.boundary for e in subdivision.edges}
    owners = {e.vertices: [] for e in subdivision.edges}
    cells = []
    boundary_spans = {i: [] for i in range(len(fp.vertices))}
    for ci, ring in enumerate(rings):
        start = min(
            range(len(ring)), key=lambda i: tuple(round(v, 10) for v in nodes[ring[i]])
        )
        ring = ring[start:] + ring[:start]
        geometric = corners(ring, nodes)
        sides = []
        for si, (a, b) in enumerate(zip(geometric, geometric[1:] + geometric[:1])):
            k = ring.index(a)
            spans = []
            artificial = []
            while ring[k] != b:
                u, v = ring[k], ring[(k + 1) % len(ring)]
                key = tuple(sorted((u, v)))
                owners[key].append((ci, si))
                edge = exterior[key]
                if edge is None:
                    artificial.append(key)
                else:
                    p = fp.vertices[edge]
                    vector = sub(fp.vertices[(edge + 1) % len(fp.vertices)], p)
                    size = sum(x * x for x in vector)
                    values = tuple(
                        sum(x * y for x, y in zip(sub(nodes[i], p), vector)) / size
                        for i in (u, v)
                    )
                    interval = (max(0.0, min(values)), min(1.0, max(values)))
                    span = BoundarySpan(edge, interval, fp.source_edges[edge])
                    if spans and spans[-1].edge == edge:
                        prev = spans.pop()
                        span = BoundarySpan(
                            edge,
                            (
                                min(prev.interval[0], interval[0]),
                                max(prev.interval[1], interval[1]),
                            ),
                            span.original_edges,
                        )
                    spans.append(span)
                k = (k + 1) % len(ring)
            for span in spans:
                boundary_spans[span.edge].append(span.interval)
            sides.append(Side((a, b), tuple(spans), tuple(artificial)))
        cells.append(Cell(ci, geometric, ring, tuple(sides)))
    adjacent = []
    for key, incident in sorted(owners.items()):
        if exterior[key] is not None:
            if len(incident) != 1:
                raise UnsupportedGraphError(
                    "exterior interval has multiple/missing cells"
                )
        else:
            if len(incident) != 2 or incident[0][0] == incident[1][0]:
                raise UnsupportedGraphError(
                    "artificial interval lacks two distinct cells"
                )
            (a, sa), (b, sb) = sorted(incident)
            adjacent.append(Adjacency((a, b), (sa, sb), key))
    for edge, spans in boundary_spans.items():
        spans.sort()
        if (
            not spans
            or abs(spans[0][0]) > EPS
            or abs(spans[-1][1] - 1) > EPS
            or any(abs(a[1] - b[0]) > EPS for a, b in zip(spans, spans[1:]))
        ):
            raise UnsupportedGraphError(
                "exterior provenance does not cover boundary exactly once"
            )
    if len(cells) != subdivision.minimum_cells:
        raise UnsupportedGraphError("cell records lost minimum rectangle count")
    return Decomposition(
        fp, nodes, tuple(cells), tuple(adjacent), 0, subdivision.certificate
    )
