# SPDX-License-Identifier: GPL-3.0-or-later
"""Metric polygon operations for the roof generator (GEOS owns overlay/noding)."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import sys
import numpy as np

_dependencies = (
    Path(__file__).resolve().parents[1]
    / ".roof-deps"
    / f"cp{sys.version_info.major}{sys.version_info.minor}"
)
if _dependencies.is_dir() and str(_dependencies) not in sys.path:
    sys.path.insert(0, str(_dependencies))

try:
    import shapely
    from shapely.geometry import (
        Polygon,
        MultiPolygon,
        GeometryCollection,
        Point,
        LineString,
    )

    if not hasattr(shapely, "orient_polygons") or not hasattr(
        shapely, "constrained_delaunay_triangles"
    ):
        raise ImportError("Shapely 2.1 or newer is required")
except ImportError as exc:
    raise ImportError(
        "Final roof generation requires Shapely 2.1.2. Install it with Roof Generator preferences → Install dependency."
    ) from exc

# All core geometry is in an intrinsic frame divided by perimeter. This grid is
# numerical tolerance only: it never changes edge directions into right angles.
GRID = 1e-11
EPS = 2e-9


class UnsupportedRoofError(ValueError):
    """The requested footprint/parameters cannot produce a validated roof."""


@dataclass(frozen=True)
class Frame2D:
    origin: tuple[float, float]
    u: tuple[float, float]
    scale: float

    def lift(self, vertices):
        p = np.asarray(vertices, dtype=float)
        u = np.asarray(self.u)
        v = np.array([-u[1], u[0]])
        xy = np.asarray(self.origin) + self.scale * (p[:, :1] * u + p[:, 1:2] * v)
        return np.column_stack((xy, p[:, 2] * self.scale))


@dataclass(frozen=True)
class Footprint:
    polygon: Polygon
    # Each normalized boundary edge maps back to one or more original edges.
    source_edges: tuple[tuple[int, ...], ...]
    frame: Frame2D


@dataclass(frozen=True)
class GeometryProperties:
    convex: bool
    parallel_opposite_pairs: tuple[tuple[int, int], ...]
    approximate_orthogonality: bool
    aspect_ratio: float

    @property
    def one_parallel_pair(self):
        return len(self.parallel_opposite_pairs) == 1


def cross(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def signed_area(points):
    p = np.asarray(points)
    # Subtract an anchor first: world-coordinate shoelace is cancellation prone.
    p = p - p[0]
    return float(sum(cross(a, b) for a, b in zip(p, np.roll(p, -1, axis=0))) / 2)


def clean_ring(points, eps=EPS):
    p = [np.asarray(x, dtype=float) for x in points]
    if len(p) > 1 and np.linalg.norm(p[0] - p[-1]) <= eps:
        p.pop()
    while len(p) > 3:
        removed = False
        for i in range(len(p)):
            a, b = p[i] - p[i - 1], p[(i + 1) % len(p)] - p[i]
            if np.linalg.norm(a) <= eps or (
                abs(cross(a, b)) <= eps * np.linalg.norm(a) and np.dot(a, b) >= 0
            ):
                p.pop(i)
                removed = True
                break
        if not removed:
            break
    if signed_area(p) < 0:
        p.reverse()
    return tuple(tuple(float(y) for y in x) for x in p)


def ring_key(poly):
    points = clean_ring(poly.exterior.coords)
    seq = tuple(tuple(round(v, 10) for v in p) for p in points)
    return min(seq[i:] + seq[:i] for i in range(len(seq)))


def normalize_footprint(vertices) -> Footprint:
    p = np.asarray(vertices, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
        raise UnsupportedRoofError(
            "footprint must be finite (n, 2) coordinates, n >= 3"
        )
    if np.array_equal(p[0], p[-1]):
        p = p[:-1]
    lengths = np.linalg.norm(np.roll(p, -1, axis=0) - p, axis=1)
    scale = float(sum(lengths))
    if not np.isfinite(scale) or scale <= 0 or np.min(lengths) <= scale * EPS:
        raise UnsupportedRoofError(
            "zero-length or numerically degenerate footprint edge"
        )
    centered = (p - p[0]) / scale
    original = Polygon(centered)
    if not original.is_valid or original.area <= EPS**2:
        raise UnsupportedRoofError(
            "footprint must be a simple positive-area loop without touching edges"
        )
    ids = list(range(len(p)))
    if signed_area(centered) < 0:
        ids.reverse()
    # Remove tolerance-collinear vertices, retaining source identity later by
    # matching original edge segments, rather than shifting edge metadata.
    while len(ids) > 3:
        removed = False
        for i in range(len(ids)):
            a = centered[ids[i]] - centered[ids[i - 1]]
            b = centered[ids[(i + 1) % len(ids)]] - centered[ids[i]]
            if abs(cross(a, b)) <= EPS * np.linalg.norm(a) and np.dot(a, b) >= 0:
                ids.pop(i)
                removed = True
                break
        if not removed:
            break
    # An invariant cyclic signature chooses the frame, including a stable tie
    # on the original traversal for genuinely symmetric polygons.
    q = centered[ids]
    edges = np.roll(q, -1, axis=0) - q
    lens = np.linalg.norm(edges, axis=1)
    dirs = edges / lens[:, None]
    sig = tuple(
        (
            round(float(lens[i]), 10),
            round(float(np.dot(dirs[i - 1], dirs[i])), 10),
            round(cross(dirs[i - 1], dirs[i]), 10),
        )
        for i in range(len(q))
    )
    start = min(range(len(q)), key=lambda i: sig[i:] + sig[:i])
    ids = ids[start:] + ids[:start]
    u = p[ids[1]] - p[ids[0]]
    u /= np.linalg.norm(u)
    v = np.array([-u[1], u[0]])
    local = (
        np.column_stack(((p[ids] - p[ids[0]]) @ u, (p[ids] - p[ids[0]]) @ v)) / scale
    )
    local = np.round(local / GRID) * GRID
    poly = Polygon(local)
    if not poly.is_valid or not poly.exterior.is_ccw:
        raise UnsupportedRoofError("normalization cannot preserve a valid polygon")
    originals_local = (
        np.column_stack(((p - p[ids[0]]) @ u, (p - p[ids[0]]) @ v)) / scale
    )
    source = []
    for a, b in zip(local, np.roll(local, -1, axis=0)):
        line = LineString([a, b])
        matches = tuple(
            i
            for i in range(len(p))
            if line.distance(Point(originals_local[i])) <= EPS
            and line.distance(Point(originals_local[(i + 1) % len(p)])) <= EPS
        )
        if not matches:
            raise UnsupportedRoofError("could not preserve source edge provenance")
        source.append(matches)
    return Footprint(poly, tuple(source), Frame2D(tuple(p[ids[0]]), tuple(u), scale))


def properties(poly):
    p = np.asarray(clean_ring(poly.exterior.coords))
    edges = np.roll(p, -1, axis=0) - p
    dirs = edges / np.linalg.norm(edges, axis=1)[:, None]
    parallel = (
        ()
        if len(p) != 4
        else tuple(
            (i, i + 2) for i in range(2) if abs(cross(dirs[i], dirs[i + 2])) <= EPS
        )
    )
    rect = np.asarray(poly.minimum_rotated_rectangle.exterior.coords)[:4]
    lengths = np.linalg.norm(np.roll(rect, -1, axis=0) - rect, axis=1)
    return GeometryProperties(
        all(
            cross(edges[i - 1], edges[i]) >= -EPS * np.linalg.norm(edges[i - 1])
            for i in range(len(p))
        ),
        parallel,
        bool(np.max(np.abs(np.sum(dirs * np.roll(dirs, -1, axis=0), axis=1))) <= EPS),
        float(max(lengths) / min(lengths)),
    )


def polygon_pieces(geometry):
    if geometry.is_empty:
        return ()
    if isinstance(geometry, Polygon):
        return (geometry,) if geometry.area > EPS * geometry.length else ()
    if isinstance(geometry, (MultiPolygon, GeometryCollection)):
        return tuple(p for g in geometry.geoms for p in polygon_pieces(g))
    return ()


def precise(geometry):
    """Snap only arithmetic roundoff; never repair invalid inputs with buffer(0)."""
    return shapely.orient_polygons(shapely.set_precision(geometry, GRID))


def clip(geometry, plane, limit=0.0):
    """Intersect with a*x + b*y + c >= limit using a bounded halfplane."""
    a, b, c = map(float, plane)
    c -= limit
    norm = math.hypot(a, b)
    if norm <= GRID:
        return geometry if c >= -GRID else Polygon()
    a, b, c = a / norm, b / norm, c / norm
    if geometry.is_empty:
        return geometry
    x0, y0, x1, y1 = geometry.bounds
    padding = max(x1 - x0, y1 - y0, EPS) * 0.1 + EPS
    ring = [
        (x0 - padding, y0 - padding),
        (x1 + padding, y0 - padding),
        (x1 + padding, y1 + padding),
        (x0 - padding, y1 + padding),
    ]
    output = []
    for p, q in zip(ring, ring[1:] + ring[:1]):
        dp, dq = a * p[0] + b * p[1] + c, a * q[0] + b * q[1] + c
        if dp >= 0:
            output.append(p)
        if (dp >= 0) != (dq >= 0):
            t = dp / (dp - dq)
            output.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    if len(output) < 3:
        return Polygon()
    halfplane = Polygon(np.round(np.asarray(output) / GRID) * GRID)
    if halfplane.area <= EPS**2:
        return Polygon()
    if not halfplane.is_valid:
        raise UnsupportedRoofError(
            "degenerate plane intersection at numerical tolerance"
        )
    return precise(geometry.intersection(precise(halfplane)))


def inward_plane(a, b):
    delta = np.asarray(b) - a
    normal = np.array([-delta[1], delta[0]]) / np.linalg.norm(delta)
    return (float(normal[0]), float(normal[1]), -float(np.dot(normal, a)))


def plane_value(plane, point):
    return float(plane[0] * point[0] + plane[1] * point[1] + plane[2])
