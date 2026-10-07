# SPDX-License-Identifier: GPL-3.0-or-later
"""Architectural part selection and shared-boundary adjacency, without roof mesh."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
import itertools
import numpy as np
import shapely
from shapely.geometry import Polygon, Point, LineString, MultiLineString
from shapely.ops import split, unary_union

from .roof_geometry import (
    EPS,
    GRID,
    Footprint,
    UnsupportedRoofError,
    polygon_ring,
    reflex_vertices,
    convex,
    ring_key,
    properties,
    cross,
    polygon_pieces,
    precise,
)


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


def _cut_signature(cut):
    return tuple(sorted(tuple(round(float(x), 10) for x in p) for p in cut))


def _partition_cost(polys, cuts, directions):
    aspects = tuple(
        sorted((round(properties(p).aspect_ratio, 8) for p in polys), reverse=True)
    )
    length = round(sum(np.linalg.norm(np.asarray(b) - a) for a, b in cuts), 10)
    deviations = []
    for a, b in cuts:
        d = np.asarray(b) - a
        d /= np.linalg.norm(d)
        deviations.append(min(abs(cross(d, edge)) for edge in directions))
    return (
        len(polys),
        aspects,
        length,
        round(sum(deviations), 10),
        tuple(sorted(_cut_signature(c) for c in cuts)),
        tuple(sorted(ring_key(p) for p in polys)),
    )


def _reflex_count(poly):
    return len(reflex_vertices(poly))


def _candidate_cuts(poly, directions, *, minimum_vertices=3):
    p = np.asarray(polygon_ring(poly))
    reflex = reflex_vertices(poly)
    starts = reflex if reflex else list(range(len(p)))
    cuts = {}
    boundary = poly.boundary
    interior = poly.buffer(EPS)
    span = max(poly.bounds[2] - poly.bounds[0], poly.bounds[3] - poly.bounds[1])
    for i in starts:
        a = p[i]
        triangle_edges = MultiLineString([
            [p[(i + 1) % len(p)], p[(i + 2) % len(p)]],
            [p[(i - 2) % len(p)], p[(i - 1) % len(p)]],
        ]) if minimum_vertices == 4 else None
        vectors = [sign * d for d in directions for sign in [-1, 1]]
        vectors += [
            p[j] - a
            for j in range(len(p))
            if j not in {i, (i - 1) % len(p), (i + 1) % len(p)}
        ]
        seen_directions = set()
        for vector in vectors:
            length = np.linalg.norm(vector)
            if length <= EPS:
                continue
            direction = vector / length
            # Repeated footprint edges and diagonals can produce exactly the
            # same ray. Deduplicate before overlay/splitting, without merging
            # nearly parallel directions or changing the candidate set.
            key = tuple(direction)
            if key in seen_directions:
                continue
            seen_directions.add(key)
            if not poly.contains(Point(a + direction * EPS * 4)):
                continue
            ray = LineString([a, a + direction * span * 3])
            hit = ray.intersection(boundary)
            points = []
            for g in shapely.get_parts(hit):
                if g.geom_type == "Point":
                    points.append(np.asarray(g.coords[0]))
                elif g.geom_type == "LineString":
                    points.extend(np.asarray(g.coords))
            hits = [
                (float(np.dot(x - a, direction)), x)
                for x in points
                if np.dot(x - a, direction) > EPS
            ]
            if not hits:
                continue
            _, b = min(hits, key=lambda x: x[0])
            # A chord hitting either next-but-one boundary edge cuts off a
            # triangle, which the gable/shed partition model rejects as a leaf.
            if triangle_edges is not None and triangle_edges.covers(Point(b)):
                continue
            if not interior.covers(LineString([a, b])):
                continue
            cutter = LineString([a - direction * EPS * 4, b + direction * EPS * 4])
            pieces = polygon_pieces(split(poly, cutter))
            if len(pieces) != 2:
                continue
            rings = tuple(polygon_ring(piece) for piece in pieces)
            if any(len(ring) < minimum_vertices for ring in rings):
                continue
            pieces = tuple(
                precise(Polygon(ring)) for ring in rings
            )
            if any(
                piece.geom_type != "Polygon"
                or not piece.is_valid
                or piece.area <= EPS**2
                for piece in pieces
            ):
                continue
            if reflex and sum(_reflex_count(piece) for piece in pieces) >= len(reflex):
                continue
            difference = unary_union(pieces).symmetric_difference(poly).area
            if difference > EPS**2 * 100:
                # Allow only overlay-scale error, not a footprint approximation.
                if difference > GRID * 10:
                    continue
            key = _cut_signature((a, b))
            cuts[key] = (tuple(map(tuple, (a, b))), pieces)
    return tuple(cuts[key] for key in sorted(cuts))


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
    cache = {}
    states = 0

    @lru_cache(maxsize=4096)
    def lower_bound(piece):
        n = len(polygon_ring(piece))
        if n == 3 and parameters.roof_type in {"gable", "shed"}:
            return float("inf")
        return (
            1 if n <= 4 and convex(piece)
            else max(2, (_reflex_count(piece) + 1) // 2 + 1)
        )

    def solve(poly):
        nonlocal states
        key = ring_key(poly)
        if key in cache:
            return cache[key]
        states += 1
        if states > max_states:
            raise UnsupportedRoofError(
                f"roof-part decomposition search exhausted {max_states} states"
            )
        vertices = polygon_ring(poly)
        if len(vertices) <= 4 and convex(poly):
            if len(vertices) == 3 and parameters.roof_type in {"gable", "shed"}:
                cache[key] = None
                return None
            cache[key] = ((poly,), ())
            return cache[key]
        best, best_cost = None, None

        candidates = _candidate_cuts(
            poly,
            directions,
            minimum_vertices=4 if parameters.roof_type in {"gable", "shed"} else 3,
        )
        candidates = sorted(
            candidates,
            key=lambda c: (sum(lower_bound(x) for x in c[1]), _cut_signature(c[0])),
        )
        for cut, (a, b) in candidates:
            bound = lower_bound(a) + lower_bound(b)
            if not np.isfinite(bound) or (
                best_cost is not None and bound > best_cost[0]
            ):
                continue
            left = solve(a)
            if left is None:
                continue
            if best_cost is not None:
                minimum = len(left[0]) + lower_bound(b)
                if minimum > best_cost[0]:
                    continue
                if minimum == best_cost[0]:
                    # Every remaining part has aspect ratio >= 1 and every
                    # remaining cut has nonnegative length. If even these
                    # optimistic values lose, solving the right side cannot
                    # improve the current lexicographic winner.
                    known = _partition_cost(left[0], left[1] + (cut,), directions)
                    aspects = tuple(sorted(
                        known[1] + (1.0,) * int(lower_bound(b)), reverse=True,
                    ))
                    if aspects > best_cost[1] or (
                        aspects == best_cost[1] and known[2] > best_cost[2]
                    ):
                        continue
            right = solve(b)
            if right is None:
                continue
            polys = left[0] + right[0]
            cuts = left[1] + right[1] + (cut,)
            cost = _partition_cost(polys, cuts, directions)
            if best_cost is None or cost < best_cost:
                best, best_cost = (polys, cuts), cost
        cache[key] = best
        return best

    solution = solve(original)
    if solution is None:
        raise UnsupportedRoofError(
            "no supported convex roof-part partition from footprint directions/reflex cuts"
        )
    polys, cuts = solution

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
                            i, j, source_edges[j], (coords[0], coords[-1])
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
        tuple(sorted(cuts, key=_cut_signature)),
        _partition_cost(polys, cuts, directions),
        states,
    )
