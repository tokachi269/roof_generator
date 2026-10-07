# SPDX-License-Identifier: GPL-3.0-or-later
"""Architectural part selection and shared-boundary adjacency, without roof mesh."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
import itertools
import numpy as np

from .roof_geometry import (
    EPS,
    GRID,
    Footprint,
    UnsupportedRoofError,
    polygon_ring,
    ring_key,
    properties,
    precise,
    inward_plane,
)
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union

from .roof_partition import partition_rings, partition_cost, cut_signature


@dataclass(frozen=True)
class RoofParameters:
    roof_type: str = "gable"
    pitch: float = 0.5  # rise/run, not degrees
    eave_height: float = 0.0
    eave_pair: tuple[int, int] | None = None
    shed_edge: int | None = None
    planes: tuple[tuple[float, float, float], ...] = ()


@dataclass(frozen=True)
class SourceEdge:
    part_edge: int
    footprint_edge: int
    original_edges: tuple[int, ...]
    segment: tuple[tuple[float, float], tuple[float, float]]
    support_line: tuple[float, float, float]


@dataclass(frozen=True)
class Neighbor:
    part_id: int
    shared_boundary: tuple[tuple[tuple[float, float], ...], ...]


@dataclass(frozen=True)
class RoofPart:
    id: int
    footprint: Polygon
    source_edges: tuple[SourceEdge, ...]
    neighbors: tuple[Neighbor, ...]
    parameters: RoofParameters
    ridge_orientation: tuple[float, float] | None = None
    plane_definitions: tuple[tuple[float, float, float], ...] = ()
    provenance: tuple[str, ...] = ()

    @property
    def geometry(self):
        return properties(self.footprint)


@dataclass(frozen=True)
class Decomposition:
    parts: tuple[RoofPart, ...]
    cuts: tuple[tuple[tuple[float, float], tuple[float, float]], ...]
    cost: tuple
    searched_states: int


def _line_pieces(geometry):
    if geometry.is_empty:
        return ()
    if geometry.geom_type == "LineString":
        return (geometry,) if geometry.length > EPS else ()
    if hasattr(geometry, "geoms"):
        return tuple(line for g in geometry.geoms for line in _line_pieces(g))
    return ()


def decompose(
    footprint: Footprint,
    parameters=RoofParameters(),
    *,
    max_states=12000,
    max_vertices=32,
):
    partition = _partition(
        footprint.polygon,
        footprint.source_edges,
        parameters.roof_type,
        max_states,
        max_vertices,
    )
    return replace(
        partition,
        parts=tuple(replace(part, parameters=parameters) for part in partition.parts),
    )


@lru_cache(maxsize=256)
def _partition(original, source_edges, roof_type, max_states, max_vertices):
    # Only immutable footprint geometry/provenance and search constraints are
    # cached. Requested pitch, heights and planes belong to the current call.
    parameters = RoofParameters(roof_type)
    if parameters.roof_type not in {"flat", "gable", "hip", "shed"}:
        raise UnsupportedRoofError("roof_type must be flat, gable, hip or shed")
    p = np.asarray(polygon_ring(original))
    if len(p) > max_vertices:
        raise UnsupportedRoofError(
            f"footprint exceeds supported search size ({max_vertices} normalized vertices)"
        )
    edges = np.roll(p, -1, axis=0) - p
    directions = edges / np.linalg.norm(edges, axis=1)[:, None]
    rings, cuts, states = partition_rings(
        polygon_ring(original),
        tuple(tuple(float(v) for v in d) for d in directions),
        parameters.roof_type,
        max_states,
    )
    polys = tuple(precise(Polygon(ring)) for ring in rings)

    def canonical_polygon(poly):
        ring = polygon_ring(poly)
        start = min(range(len(ring)), key=lambda i: tuple(ring[i:] + ring[:i]))
        return precise(Polygon(ring[start:] + ring[:start]))

    polys = tuple(canonical_polygon(poly) for poly in sorted(polys, key=ring_key))
    if unary_union(polys).symmetric_difference(original).area > EPS:
        raise UnsupportedRoofError(
            "part partition does not exactly cover the footprint"
        )
    for a, b in itertools.combinations(polys, 2):
        if a.intersection(b).area > EPS**2 * 100:
            raise UnsupportedRoofError("part interiors overlap")
    neighbors = [[] for _ in polys]
    for i, j in itertools.combinations(range(len(polys)), 2):
        lines = _line_pieces(
            precise(polys[i].boundary).intersection(precise(polys[j].boundary))
        )
        if lines:
            boundary = tuple(tuple(tuple(v) for v in line.coords) for line in lines)
            neighbors[i].append(Neighbor(j, boundary))
            neighbors[j].append(Neighbor(i, boundary))
    sources = []
    original_edges = [LineString([p[i], p[(i + 1) % len(p)]]) for i in range(len(p))]
    for poly in polys:
        part_sources = []
        ring = np.asarray(poly.exterior.coords)[:-1]
        for i in range(len(ring)):
            edge = precise(LineString([ring[i], ring[(i + 1) % len(ring)]]))
            for j, orig in enumerate(original_edges):
                for line in _line_pieces(edge.intersection(precise(orig))):
                    coords = tuple(map(tuple, line.coords))
                    part_sources.append(
                        SourceEdge(
                            i,
                            j,
                            source_edges[j],
                            (coords[0], coords[-1]),
                            inward_plane(p[j], p[(j + 1) % len(p)]),
                        )
                    )
        sources.append(tuple(part_sources))
    parts = tuple(
        RoofPart(
            i,
            poly,
            sources[i],
            tuple(neighbors[i]),
            parameters,
            provenance=(
                "reflex/direction partition",
                "lexicographic count/aspect/cut/direction/signature",
            ),
        )
        for i, poly in enumerate(polys)
    )
    return Decomposition(
        parts,
        tuple(sorted(cuts, key=cut_signature)),
        partition_cost(tuple(polygon_ring(poly) for poly in polys), cuts, directions),
        states,
    )
