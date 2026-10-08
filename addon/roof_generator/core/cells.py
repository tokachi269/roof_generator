# SPDX-License-Identifier: GPL-3.0-or-later
"""Roof-independent Cell/Side/Adjacency conversion of classical minimum partitions."""

from dataclasses import dataclass, asdict
from .footprint import EPS, sub, Footprint
from .provenance import BoundarySpan
from .errors import UnsupportedRoofError
from .partition import partition, Subdivision, PartitionCertificate, corners


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
    footprint: Footprint
    vertices: tuple[tuple[float, float], ...]
    cells: tuple[Cell, ...]
    adjacency: tuple[Adjacency, ...]
    certificate: PartitionCertificate | None = None

    def inspect(self):
        return {
            "vertices": self.vertices,
            "cells": [asdict(c) for c in self.cells],
            "adjacency": [asdict(a) for a in self.adjacency],
            "certificate": asdict(self.certificate) if self.certificate else None,
        }


def _signature(ring, nodes):
    points = tuple(tuple(round(x, 10) for x in nodes[i]) for i in ring)
    return min(points[i:] + points[:i] for i in range(len(points)))


def decompose(fp):
    return from_subdivision(fp, partition(fp))


def _boundary_span(fp, nodes, u, v, edge):
    """Exterior provenance of one atomic segment."""
    p = fp.vertices[edge]
    vector = sub(fp.vertices[(edge + 1) % len(fp.vertices)], p)
    size = sum(x * x for x in vector)
    values = tuple(
        sum(x * y for x, y in zip(sub(nodes[i], p), vector)) / size for i in (u, v)
    )
    interval = (max(0.0, min(values)), min(1.0, max(values)))
    return BoundarySpan(edge, interval, fp.source_edges[edge])


def _validate_provenance(boundary_spans):
    """Every original exterior edge is owned exactly once."""
    for edge, spans in boundary_spans.items():
        spans.sort()
        if (
            not spans
            or abs(spans[0][0]) > EPS
            or abs(spans[-1][1] - 1) > EPS
            or any(abs(a[1] - b[0]) > EPS for a, b in zip(spans, spans[1:]))
        ):
            raise UnsupportedRoofError(
                "exterior provenance does not cover boundary exactly once"
            )


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
                    span = _boundary_span(fp, nodes, u, v, edge)
                    interval = span.interval
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
                raise UnsupportedRoofError(
                    "exterior interval has multiple/missing cells"
                )
        else:
            if len(incident) != 2 or incident[0][0] == incident[1][0]:
                raise UnsupportedRoofError(
                    "artificial interval lacks two distinct cells"
                )
            (a, sa), (b, sb) = sorted(incident)
            adjacent.append(Adjacency((a, b), (sa, sb), key))
    _validate_provenance(boundary_spans)
    if len(cells) != subdivision.minimum_cells:
        raise UnsupportedRoofError("cell records lost minimum rectangle count")
    return Decomposition(
        fp, nodes, tuple(cells), tuple(adjacent), subdivision.certificate
    )


def single_cell(fp):
    """One convex quadrilateral; no rectangular partition theorem is claimed."""
    if len(fp.vertices) != 4 or fp.reflex:
        raise UnsupportedRoofError(
            "generalized decomposition currently requires a convex quadrilateral"
        )
    spans = tuple(BoundarySpan(i, (0.0, 1.0), fp.source_edges[i]) for i in range(4))
    sides = tuple(Side((i, (i + 1) % 4), (spans[i],), ()) for i in range(4))
    ring = tuple(range(4))
    return Decomposition(fp, fp.vertices, (Cell(0, ring, ring, sides),), ())
