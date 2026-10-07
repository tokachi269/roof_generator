# SPDX-License-Identifier: GPL-3.0-or-later
"""Select roof-part topology using ordered rings and chords, without polygons."""

from functools import lru_cache
import math
from .roof_geometry import (
    EPS,
    GRID,
    UnsupportedRoofError,
    clean_ring,
    cross,
    bounding_aspect,
)


def cut_signature(cut):
    return tuple(sorted(tuple(round(float(x), 10) for x in p) for p in cut))


def _ring_key(ring):
    seq = tuple(tuple(round(v, 10) for v in p) for p in ring)
    return min(seq[i:] + seq[:i] for i in range(len(seq)))


@lru_cache(maxsize=4096)
def _reflex_vertices(ring):
    return tuple(
        i
        for i, p in enumerate(ring)
        if cross(
            (p[0] - ring[i - 1][0], p[1] - ring[i - 1][1]),
            (ring[(i + 1) % len(ring)][0] - p[0], ring[(i + 1) % len(ring)][1] - p[1]),
        )
        < -EPS * math.dist(p, ring[i - 1])
    )


def _area(ring):
    ox, oy = ring[0]
    return (
        sum(
            (a[0] - ox) * (b[1] - oy) - (a[1] - oy) * (b[0] - ox)
            for a, b in zip(ring, ring[1:] + ring[:1])
        )
        / 2
    )


def partition_cost(rings, cuts, directions):
    aspects = tuple(
        sorted((round(bounding_aspect(ring), 8) for ring in rings), reverse=True)
    )
    length = round(sum(math.dist(a, b) for a, b in cuts), 10)
    deviations = []
    for a, b in cuts:
        size = math.dist(a, b)
        d = ((b[0] - a[0]) / size, (b[1] - a[1]) / size)
        deviations.append(min(abs(cross(d, edge)) for edge in directions))
    return (
        len(rings),
        aspects,
        length,
        round(sum(deviations), 10),
        tuple(sorted(cut_signature(c) for c in cuts)),
        tuple(sorted(_ring_key(ring) for ring in rings)),
    )


def _strictly_inside(point, ring):
    # Used only when cleanup removes a chord endpoint. Do not allow a cleanup
    # shortcut to move the shared boundary into the neighbor's interior.
    inside = False
    px, py = point
    for a, b in zip(ring, ring[1:] + ring[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        vx, vy = px - a[0], py - a[1]
        length = math.hypot(dx, dy)
        determinant = dx * vy - dy * vx
        t = (vx * dx + vy * dy) / (length * length)
        if 0 <= t <= 1 and abs(determinant) <= GRID * length:
            return False
        if (a[1] > py) != (b[1] > py) and px < a[0] + dx * (py - a[1]) / dy:
            inside = not inside
    return inside


def _ray_hit(points, start, direction):
    """First positive boundary hit; returns its position and containing edge.

    The ray starts inside the vertex wedge. Traversal therefore ends at its
    first boundary contact, including a grazing vertex or collinear segment.
    This is a known polygon chord, not a general polygon Boolean operation.
    """
    ax, ay = points[start]
    dx, dy = direction
    best = None
    for j, q in enumerate(points):
        if j in {start, (start - 1) % len(points)}:
            continue
        r = points[(j + 1) % len(points)]
        ex, ey = r[0] - q[0], r[1] - q[1]
        qx, qy = q[0] - ax, q[1] - ay
        denominator = dx * ey - dy * ex
        # Roundoff allowance, relative to this edge's length. Architectural
        # tolerance is not used to merge distinct near-parallel directions.
        roundoff = 32 * math.ulp(1.0) * math.hypot(ex, ey)
        if abs(denominator) <= roundoff:
            if abs(qx * dy - qy * dx) > roundoff:
                continue
            for point in (q, r):
                t = (point[0] - ax) * dx + (point[1] - ay) * dy
                if t > EPS and (best is None or t < best[0]):
                    best = (t, point, j)
            continue
        t = (qx * ey - qy * ex) / denominator
        u = (qx * dy - qy * dx) / denominator
        margin = 32 * math.ulp(1.0) * max(1, abs(t), abs(u))
        if t <= EPS or u < -margin or u > 1 + margin:
            continue
        point = (
            q
            if abs(u) <= margin
            else (
                r
                if abs(u - 1) <= margin
                else (
                    ax + t * dx,
                    ay + t * dy,
                )
            )
        )
        if best is None or t < best[0]:
            best = (t, point, j)
    return best


def candidate_cuts(points, directions, *, minimum_vertices=3):
    reflex = _reflex_vertices(points)
    starts = reflex if reflex else range(len(points))
    cuts = {}
    vectors = tuple((sign * d[0], sign * d[1]) for d in directions for sign in (-1, 1))
    for i in starts:
        a = points[i]
        before, after = points[i - 1], points[(i + 1) % len(points)]
        incoming = (a[0] - before[0], a[1] - before[1])
        outgoing = (after[0] - a[0], after[1] - a[1])
        diagonals = tuple(
            (p[0] - a[0], p[1] - a[1])
            for j, p in enumerate(points)
            if j not in {i, (i - 1) % len(points), (i + 1) % len(points)}
        )
        seen = set()
        for vector in vectors + diagonals:
            length = math.hypot(*vector)
            if length <= EPS:
                continue
            direction = (vector[0] / length, vector[1] / length)
            if direction in seen:
                continue
            seen.add(direction)
            left_in, left_out = cross(incoming, direction), cross(outgoing, direction)
            # A CCW convex wedge is an intersection; a reflex wedge is a union.
            # Strict interior entry excludes rays following the actual boundary.
            error = (
                32 * math.ulp(1.0) * max(math.hypot(*incoming), math.hypot(*outgoing))
            )
            enters = (
                (left_in > error or left_out > error)
                if i in reflex
                else (left_in > error and left_out > error)
            )
            if not enters:
                continue
            hit = _ray_hit(points, i, direction)
            if hit is None:
                continue
            _, b, j = hit
            key = cut_signature((a, b))
            # Splitting at the first contact follows each original boundary
            # arc once. Both children share the exact same cut endpoints.
            k = (j - i) % len(points)
            if min(k + 2, len(points) - k + 1) < minimum_vertices:
                continue
            walk = points[i:] + points[:i]
            rings = (
                clean_ring(walk[: k + 1] + (b,)),
                clean_ring((b,) + walk[k + 1 :] + (a,)),
            )
            if any(len(ring) < minimum_vertices for ring in rings):
                continue
            rings = tuple(
                tuple(
                    (
                        math.floor(x / GRID + 0.5) * GRID,
                        math.floor(y / GRID + 0.5) * GRID,
                    )
                    for x, y in ring
                )
                for ring in rings
            )
            if any(_area(ring) <= EPS**2 for ring in rings):
                continue
            endpoints = tuple(
                (math.floor(x / GRID + 0.5) * GRID, math.floor(y / GRID + 0.5) * GRID)
                for x, y in (a, b)
            )
            if any(
                _strictly_inside(point, ring)
                for ring in rings
                for point in endpoints
                if point not in ring
            ):
                continue
            if reflex and sum(len(_reflex_vertices(ring)) for ring in rings) >= len(
                reflex
            ):
                continue
            if abs(sum(_area(ring) for ring in rings) - _area(points)) > GRID * 10:
                continue
            cuts[key] = (tuple((a, b)), rings)
    return tuple(cuts[key] for key in sorted(cuts))


def partition_rings(points, directions, roof_type, max_states):
    cache = {}
    states = 0

    @lru_cache(maxsize=None)
    def lower_bound(piece):
        n = len(piece)
        if n == 3 and roof_type in {"gable", "shed"}:
            return float("inf")
        return (
            1
            if n <= 4 and not _reflex_vertices(piece)
            else max(2, (len(_reflex_vertices(piece)) + 1) // 2 + 1)
        )

    def solve(poly):
        nonlocal states
        key = _ring_key(poly)
        if key in cache:
            return cache[key]
        states += 1
        if states > max_states:
            raise UnsupportedRoofError(
                f"roof-part decomposition search exhausted {max_states} states"
            )
        vertices = poly
        if len(vertices) <= 4 and not _reflex_vertices(poly):
            if len(vertices) == 3 and roof_type in {"gable", "shed"}:
                cache[key] = None
                return None
            cache[key] = ((poly,), ())
            return cache[key]
        best, best_cost = None, None

        candidates = candidate_cuts(
            poly,
            directions,
            minimum_vertices=4 if roof_type in {"gable", "shed"} else 3,
        )
        candidates = sorted(
            candidates,
            key=lambda c: (sum(lower_bound(x) for x in c[1]), cut_signature(c[0])),
        )
        for cut, (a, b) in candidates:
            bound = lower_bound(a) + lower_bound(b)
            if not math.isfinite(bound) or (
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
                    known = partition_cost(left[0], left[1] + (cut,), directions)
                    aspects = tuple(
                        sorted(
                            known[1] + (1.0,) * int(lower_bound(b)),
                            reverse=True,
                        )
                    )
                    if aspects > best_cost[1] or (
                        aspects == best_cost[1] and known[2] > best_cost[2]
                    ):
                        continue
            right = solve(b)
            if right is None:
                continue
            polys = left[0] + right[0]
            cuts = left[1] + right[1] + (cut,)
            cost = partition_cost(polys, cuts, directions)
            if best_cost is None or cost < best_cost:
                best, best_cost = (polys, cuts), cost
        cache[key] = best
        return best

    solution = solve(points)
    if solution is None:
        raise UnsupportedRoofError(
            "no supported convex roof-part partition from footprint directions/reflex cuts"
        )
    rings, cuts = solution
    return rings, cuts, states
