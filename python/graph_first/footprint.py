# SPDX-License-Identifier: GPL-3.0-or-later
"""Scalar outline analysis and visibility, independent of polygon libraries."""

from dataclasses import dataclass
import math
from .graph import Point, UnsupportedGraphError

EPS = 2e-9  # normalized by perimeter; numerical allowance, not rectification
ANGLE = 1e-8


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def sub(a, b):
    return a[0] - b[0], a[1] - b[1]


def area(points):
    origin = points[0]
    return (
        sum(
            cross(sub(a, origin), sub(b, origin))
            for a, b in zip(points, points[1:] + points[:1])
        )
        / 2
    )


def on_segment(p, a, b):
    d, v = sub(b, a), sub(p, a)
    size = math.hypot(*d)
    if size <= EPS:
        return math.dist(p, a) <= EPS
    t = (v[0] * d[0] + v[1] * d[1]) / size**2
    return -EPS / size <= t <= 1 + EPS / size and abs(cross(d, v)) <= EPS * size


def inside(p, ring):
    if any(on_segment(p, a, b) for a, b in zip(ring, ring[1:] + ring[:1])):
        return False
    return (
        sum(
            (a[1] > p[1]) != (b[1] > p[1])
            and p[0] < a[0] + (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1])
            for a, b in zip(ring, ring[1:] + ring[:1])
        )
        % 2
        == 1
    )


def _intersects(a, b, c, d):
    if any(
        on_segment(p, u, v) for p, u, v in ((a, c, d), (b, c, d), (c, a, b), (d, a, b))
    ):
        return True
    return (
        cross(sub(b, a), sub(c, a)) * cross(sub(b, a), sub(d, a)) < 0
        and cross(sub(d, c), sub(a, c)) * cross(sub(d, c), sub(b, c)) < 0
    )


@dataclass(frozen=True)
class Frame:
    origin: Point
    direction: Point
    scale: float

    def world_xy(self, p):
        ux, uy = self.direction
        return self.origin[0] + self.scale * (ux * p[0] - uy * p[1]), self.origin[
            1
        ] + self.scale * (uy * p[0] + ux * p[1])

    def world_xyz(self, p):
        return (*self.world_xy(p[:2]), p[2] * self.scale)


@dataclass(frozen=True)
class Footprint:
    vertices: tuple[Point, ...]
    source_edges: tuple[tuple[int, ...], ...]
    directions: tuple[Point, ...]
    reflex: tuple[int, ...]
    parallel: tuple[tuple[int, int], ...]
    orthogonal: bool
    frame: Frame


def analyze(points):
    try:
        raw = tuple(tuple(float(v) for v in p) for p in points)
    except (TypeError, ValueError) as exc:
        raise UnsupportedGraphError("outline must be finite ordered XY points") from exc
    if raw and raw[0] == raw[-1]:
        raw = raw[:-1]
    if len(raw) < 3 or any(
        len(p) != 2 or not all(math.isfinite(v) for v in p) for p in raw
    ):
        raise UnsupportedGraphError("outline must be finite ordered XY points")
    scale = sum(math.dist(a, b) for a, b in zip(raw, raw[1:] + raw[:1]))
    if (
        not math.isfinite(scale)
        or scale <= 0
        or any(math.dist(a, b) <= scale * EPS for a, b in zip(raw, raw[1:] + raw[:1]))
    ):
        raise UnsupportedGraphError("zero-length outline edge")
    centered = tuple(
        ((p[0] - raw[0][0]) / scale, (p[1] - raw[0][1]) / scale) for p in raw
    )
    if abs(area(centered)) <= EPS**2:
        raise UnsupportedGraphError("zero-area outline")
    n = len(raw)
    for i in range(n):
        for j in range(i + 1, n):
            if j in ((i + 1) % n, (i - 1) % n):
                continue
            if _intersects(
                centered[i], centered[(i + 1) % n], centered[j], centered[(j + 1) % n]
            ):
                raise UnsupportedGraphError("outline self-intersection or touching")
    forward = area(centered) > 0
    ids = list(range(n)) if forward else list(reversed(range(n)))
    while len(ids) > 3:
        for k, i in enumerate(ids):
            a = sub(centered[i], centered[ids[k - 1]])
            b = sub(centered[ids[(k + 1) % len(ids)]], centered[i])
            if (
                abs(cross(a, b)) <= EPS * math.hypot(*a)
                and a[0] * b[0] + a[1] * b[1] >= 0
            ):
                ids.pop(k)
                break
        else:
            break
    ring = tuple(centered[i] for i in ids)
    edges = tuple(sub(b, a) for a, b in zip(ring, ring[1:] + ring[:1]))
    directions = tuple((x / math.hypot(x, y), y / math.hypot(x, y)) for x, y in edges)
    signature = tuple(
        (
            round(math.hypot(*edges[i]), 10),
            round(sum(a * b for a, b in zip(directions[i - 1], directions[i])), 10),
            round(cross(directions[i - 1], directions[i]), 10),
        )
        for i in range(len(ids))
    )
    start = min(range(len(ids)), key=lambda i: signature[i:] + signature[:i])
    ids = ids[start:] + ids[:start]
    d = sub(raw[ids[1]], raw[ids[0]])
    size = math.hypot(*d)
    u = d[0] / size, d[1] / size
    frame = Frame(raw[ids[0]], u, scale)
    vertices = tuple(
        (
            (p[0] - frame.origin[0]) * u[0] / scale
            + (p[1] - frame.origin[1]) * u[1] / scale,
            -(p[0] - frame.origin[0]) * u[1] / scale
            + (p[1] - frame.origin[1]) * u[0] / scale,
        )
        for p in (raw[i] for i in ids)
    )
    sources = []
    for a, b in zip(ids, ids[1:] + ids[:1]):
        current, originals = a, []
        while current != b:
            nxt = (current + (1 if forward else -1)) % n
            originals.append(current if forward else nxt)
            current = nxt
        sources.append(tuple(sorted(originals)))
    directions = tuple(
        (d[0] / math.hypot(*d), d[1] / math.hypot(*d))
        for d in (sub(b, a) for a, b in zip(vertices, vertices[1:] + vertices[:1]))
    )
    reflex = tuple(
        i
        for i in range(len(vertices))
        if cross(directions[i - 1], directions[i]) < -ANGLE
    )
    parallel = tuple(
        (i, j)
        for i in range(len(vertices))
        for j in range(i + 1, len(vertices))
        if abs(cross(directions[i], directions[j])) <= ANGLE
    )
    orthogonal = all(min(abs(d[0]), abs(d[1])) <= ANGLE for d in directions)
    return Footprint(
        vertices, tuple(sources), directions, reflex, parallel, orthogonal, frame
    )


def rectangle(points):
    if len(points) != 4 or area(points) <= 0:
        return False
    vectors = tuple(sub(b, a) for a, b in zip(points, points[1:] + points[:1]))
    return all(
        cross(vectors[i - 1], vectors[i]) > 0
        and abs(sum(a * b for a, b in zip(vectors[i - 1], vectors[i])))
        <= ANGLE * math.hypot(*vectors[i - 1]) * math.hypot(*vectors[i])
        for i in range(4)
    )


def ray_hit(ring, vertex, direction):
    origin = ring[vertex]
    best = None
    for j, a in enumerate(ring):
        b = ring[(j + 1) % len(ring)]
        if j in (vertex, (vertex - 1) % len(ring)):
            continue
        edge, offset = sub(b, a), sub(a, origin)
        determinant = cross(direction, edge)
        if abs(determinant) <= EPS * math.hypot(*edge):
            continue
        t, u = cross(offset, edge) / determinant, cross(offset, direction) / determinant
        if t > EPS and -EPS <= u <= 1 + EPS and (best is None or t < best[0]):
            p = (
                a
                if abs(u) <= EPS
                else (
                    b
                    if abs(u - 1) <= EPS
                    else (origin[0] + t * direction[0], origin[1] + t * direction[1])
                )
            )
            best = t, p, j
    if best is not None and inside(
        ((origin[0] + best[1][0]) / 2, (origin[1] + best[1][1]) / 2), ring
    ):
        return best[1:]
    return None
