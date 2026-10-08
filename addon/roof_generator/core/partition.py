# SPDX-License-Identifier: GPL-3.0-or-later
"""Classical good-diagonal minimum rectangular partition; no roof decisions."""

from dataclasses import dataclass
from collections import deque
import math
from .footprint import (
    EPS,
    inside,
    on_segment,
    ray_hit,
    _intersects,
    sub,
    cross,
    area,
    rectangle,
)
from .errors import UnsupportedRoofError


@dataclass(frozen=True)
class Diagonal:
    endpoints: tuple[int, int]
    axis: int  # 0 horizontal, 1 vertical in the intrinsic frame


def good_diagonals(fp):
    """All open-interior reflex chords, via their first boundary hits.

    A farther boundary vertex cannot be a valid endpoint: the open chord would
    already touch the first one. This is enumeration, not partition selection.
    """
    if not fp.orthogonal:
        raise UnsupportedRoofError("rectangle partition requires an orthogonal outline")
    if len(fp.vertices) != 2 * len(fp.reflex) + 4:
        raise UnsupportedRoofError(
            "outline does not satisfy the simple orthogonal corner identity"
        )
    result = set()
    for start in fp.reflex:
        directions = (fp.directions[start - 1], tuple(-v for v in fp.directions[start]))
        for direction in directions:
            hit = ray_hit(fp.vertices, start, direction)
            if hit is None:
                continue
            point, _ = hit
            end = next(
                (i for i in fp.reflex if math.dist(fp.vertices[i], point) <= EPS), None
            )
            if end is None or start == end:
                continue
            # The first-hit contract already excludes all intermediate
            # boundary contacts. Each endpoint of a parallel boundary edge
            # has a perpendicular incident edge and is included in the scan.
            # Rechecking every boundary segment here would duplicate visibility.
            axis = int(abs(direction[1]) > abs(direction[0]))
            result.add(Diagonal(tuple(sorted((start, end))), axis))

    def key(diagonal):
        return diagonal.axis, tuple(
            sorted(
                tuple(round(x, 10) for x in fp.vertices[i]) for i in diagonal.endpoints
            )
        )

    return tuple(sorted(result, key=key))


@dataclass(frozen=True)
class Selection:
    diagonals: tuple[Diagonal, ...]
    conflicts: tuple[tuple[int, int], ...]
    matching: tuple[tuple[int, int], ...]
    selected: tuple[int, ...]


def maximum_matching(left, right, conflicts):
    """Hopcroft–Karp with iterative layered augmenting walks (no recursion)."""
    neighbors = {h: [] for h in left}
    for h, v in conflicts:
        if h not in neighbors or v not in right:
            raise UnsupportedRoofError("conflict graph is not bipartite")
        neighbors[h].append(v)
    neighbors = {h: tuple(sorted(set(values))) for h, values in neighbors.items()}
    pair_h = {h: None for h in left}
    pair_v = {v: None for v in right}
    infinity = len(left) + len(right) + 1
    while True:
        distance = {h: (0 if pair_h[h] is None else infinity) for h in left}
        queue = deque(h for h in left if pair_h[h] is None)
        shortest = infinity
        while queue:
            h = queue.popleft()
            if distance[h] >= shortest:
                continue
            for v in neighbors[h]:
                other = pair_v[v]
                if other is None:
                    shortest = distance[h] + 1
                elif distance[other] == infinity:
                    distance[other] = distance[h] + 1
                    queue.append(other)
        if shortest == infinity:
            break
        cursor = {h: 0 for h in left}
        for root in left:
            if pair_h[root] is not None:
                continue
            stack = [root]
            while stack:
                h = stack[-1]
                while cursor[h] < len(neighbors[h]):
                    v = neighbors[h][cursor[h]]
                    cursor[h] += 1
                    other = pair_v[v]
                    if other is None and distance[h] + 1 == shortest:
                        for vertex in reversed(stack):
                            old = pair_h[vertex]
                            pair_h[vertex] = v
                            pair_v[v] = vertex
                            v = old
                        stack.clear()
                        break
                    if (
                        other is not None
                        and distance[other] == distance[h] + 1
                        and distance[other] < shortest
                    ):
                        stack.append(other)
                        break
                else:
                    distance[h] = infinity
                    stack.pop()
    return tuple((h, pair_h[h]) for h in left if pair_h[h] is not None)


def independent_set(left, right, conflicts, matching):
    """Complement of König's alternating-reachability minimum vertex cover."""
    adjacent = {h: [] for h in left}
    for h, v in conflicts:
        adjacent[h].append(v)
    pair_h = dict(matching)
    pair_v = {v: h for h, v in matching}
    reached_h = {h for h in left if h not in pair_h}
    reached_v = set()
    queue = deque(sorted(reached_h))
    while queue:
        h = queue.popleft()
        for v in adjacent[h]:
            if pair_h.get(h) == v or v in reached_v:
                continue
            reached_v.add(v)
            other = pair_v.get(v)
            if other is not None and other not in reached_h:
                reached_h.add(other)
                queue.append(other)
    selected = tuple(sorted(reached_h.union(set(right) - reached_v)))
    if len(selected) != len(left) + len(right) - len(matching) or any(
        h in selected and v in selected for h, v in conflicts
    ):
        raise UnsupportedRoofError(
            "matching does not certify a maximum independent set"
        )
    return selected


def intersection_graph(fp, diagonals):
    left = tuple(i for i, d in enumerate(diagonals) if d.axis == 0)
    right = tuple(i for i, d in enumerate(diagonals) if d.axis == 1)
    conflicts = []
    for i, a in enumerate(diagonals):
        for j, b in enumerate(diagonals[:i]):
            if not _intersects(*(fp.vertices[k] for k in a.endpoints + b.endpoints)):
                continue
            if a.axis == b.axis:
                raise UnsupportedRoofError(
                    "same-axis diagonals intersect: invalid open-interior chord"
                )
            conflicts.append((j, i) if b.axis == 0 else (i, j))
    conflicts = tuple(sorted(conflicts))
    return left, right, conflicts


def select_diagonals(fp, diagonals):
    left, right, conflicts = intersection_graph(fp, diagonals)
    matching = maximum_matching(left, right, conflicts)
    selected = independent_set(left, right, conflicts, matching)
    return Selection(diagonals, conflicts, matching, selected)


@dataclass(frozen=True)
class Cut:
    source: int
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass(frozen=True)
class AtomicEdge:
    vertices: tuple[int, int]
    boundary: int | None


@dataclass(frozen=True)
class PartitionCertificate:
    reflex: tuple[int, ...]
    selection: Selection
    completions: tuple[Cut, ...]
    minimum_cells: int


@dataclass(frozen=True)
class Subdivision:
    vertices: tuple[tuple[float, float], ...]
    faces: tuple[tuple[int, ...], ...]
    edges: tuple[AtomicEdge, ...]
    reflex: tuple[int, ...]
    selection: Selection
    completions: tuple[Cut, ...]

    @property
    def certificate(self):
        return PartitionCertificate(
            self.reflex, self.selection, self.completions, self.minimum_cells
        )

    @property
    def minimum_cells(self):
        return len(self.reflex) - len(self.selection.selected) + 1


def complete_cuts(fp, selection, axes=()):
    """Classical bad-vertex completion: first side of the current region."""
    segments = [
        tuple(fp.vertices[v] for v in selection.diagonals[i].endpoints)
        for i in selection.selected
    ]
    covered = {v for i in selection.selected for v in selection.diagonals[i].endpoints}
    completions = []
    starts = sorted(
        set(fp.reflex) - covered,
        key=lambda i: tuple(round(v, 10) for v in fp.vertices[i]),
    )
    if axes and (len(axes) != len(starts) or any(a not in (0, 1) for a in axes)):
        raise UnsupportedRoofError("completion axes must cover unresolved reflexes")
    for k, start in enumerate(starts):
        p = fp.vertices[start]
        if any(on_segment(p, a, b) for a, b in segments):
            raise UnsupportedRoofError(
                "unresolved reflex already lies on a partition cut"
            )
        direction = max(
            (fp.directions[start - 1], tuple(-v for v in fp.directions[start])),
            key=lambda d: abs(d[axes[k] if axes else 1]),
        )
        hit = ray_hit(fp.vertices, start, direction)
        if hit is None:
            raise UnsupportedRoofError("reflex extension has no visible boundary")
        end, _ = hit
        best = math.dist(p, end)
        for a, b in segments:
            edge, offset = sub(b, a), sub(a, p)
            determinant = cross(direction, edge)
            if abs(determinant) <= EPS * math.hypot(*edge):
                if abs(cross(direction, offset)) > EPS:
                    continue
                choices = [
                    (sum(v * d for v, d in zip(sub(q, p), direction)), q)
                    for q in (a, b)
                ]
                choices = [(t, q) for t, q in choices if t > EPS]
                if not choices:
                    continue
                t, point = min(choices)
            else:
                t = cross(offset, edge) / determinant
                u = cross(offset, direction) / determinant
                if t <= EPS or u < -EPS or u > 1 + EPS:
                    continue
                point = (
                    a
                    if abs(u) <= EPS
                    else (
                        b
                        if abs(u - 1) <= EPS
                        else tuple(p[k] + t * direction[k] for k in (0, 1))
                    )
                )
            if t < best - EPS:
                best, end = t, point
        if best <= EPS or not inside(
            tuple((a + b) / 2 for a, b in zip(p, end)), fp.vertices
        ):
            raise UnsupportedRoofError(
                "reflex completion is not a nonzero interior segment"
            )
        completions.append(Cut(start, p, end))
        segments.append((p, end))
    return tuple(completions)


def corners(boundary, nodes):
    """Geometric corners only; preserve the separate noded face boundary."""
    result = []
    for k, v in enumerate(boundary):
        a = sub(nodes[v], nodes[boundary[k - 1]])
        b = sub(nodes[boundary[(k + 1) % len(boundary)]], nodes[v])
        if (
            abs(cross(a, b)) > EPS * math.hypot(*a)
            or sum(x * y for x, y in zip(a, b)) < 0
        ):
            result.append(v)
    return tuple(result)


def subdivide(fp, selection, completions):
    """Node selected cuts and enumerate their bounded planar face cycles.

    Input is a fixed set of noncrossing orthogonal cuts. This is not a polygon
    Boolean, rasterization or a search over polygon subdivisions.
    """
    cut_points = [
        tuple(fp.vertices[v] for v in selection.diagonals[i].endpoints)
        for i in selection.selected
    ] + [(c.start, c.end) for c in completions]
    nodes = list(fp.vertices)
    for point in sorted(
        (p for cut in cut_points for p in cut),
        key=lambda p: tuple(round(v, 10) for v in p),
    ):
        if not any(math.dist(p, point) <= EPS for p in nodes):
            nodes.append(point)
    segments = [
        (fp.vertices[i], fp.vertices[(i + 1) % len(fp.vertices)], i)
        for i in range(len(fp.vertices))
    ] + [(a, b, None) for a, b in cut_points]
    edges = {}
    for a, b, exterior in segments:
        direction = sub(b, a)
        ids = sorted(
            (i for i, p in enumerate(nodes) if on_segment(p, a, b)),
            key=lambda i: sum(v * d for v, d in zip(sub(nodes[i], a), direction)),
        )
        for u, v in zip(ids, ids[1:]):
            key = tuple(sorted((u, v)))
            if math.dist(nodes[u], nodes[v]) <= EPS or key in edges:
                raise UnsupportedRoofError(
                    "partition contains duplicate/zero atomic segment"
                )
            edges[key] = exterior
    neighbors = {i: [] for i in range(len(nodes))}
    for a, b in edges:
        neighbors[a].append(b)
        neighbors[b].append(a)
    for i, values in neighbors.items():
        if len(values) < 2:
            raise UnsupportedRoofError("dangling partition cut")
        values.sort(
            key=lambda j: math.atan2(
                nodes[j][1] - nodes[i][1], nodes[j][0] - nodes[i][0]
            )
        )
    successor = {
        (a, b): (b, neighbors[b][(neighbors[b].index(a) - 1) % len(neighbors[b])])
        for a in neighbors
        for b in neighbors[a]
    }
    visited = set()
    faces = []
    outside = 0
    for initial in sorted(successor):
        if initial in visited:
            continue
        edge = initial
        ring = []
        while edge not in visited:
            visited.add(edge)
            ring.append(edge[0])
            edge = successor[edge]
        if edge != initial:
            raise UnsupportedRoofError("partition half-edge walk is not a cycle")
        signed = area(tuple(nodes[i] for i in ring))
        if signed < -(EPS**2):
            outside += 1
        elif signed > EPS**2:
            geometric = corners(ring, nodes)
            if not rectangle(tuple(nodes[i] for i in geometric)):
                raise UnsupportedRoofError(
                    "unresolved reflex/nonrectangle partition face"
                )
            faces.append(tuple(ring))
        else:
            raise UnsupportedRoofError("zero-area partition cycle")
    expected = len(fp.reflex) - len(selection.selected) + 1
    if (
        outside != 1
        or len(faces) != expected
        or len(nodes) - len(edges) + len(faces) != 1
    ):
        raise UnsupportedRoofError(
            "partition does not attain the minimum rectangle certificate"
        )
    if any(len(neighbors[v]) < 3 for v in fp.reflex):
        raise UnsupportedRoofError("unresolved original reflex vertex")
    if (
        abs(sum(area(tuple(nodes[i] for i in f)) for f in faces) - area(fp.vertices))
        > EPS
    ):
        raise UnsupportedRoofError("partition face area differs from footprint")
    return Subdivision(
        tuple(nodes),
        tuple(faces),
        tuple(AtomicEdge(key, value) for key, value in sorted(edges.items())),
        fp.reflex,
        selection,
        completions,
    )


def partition(fp):
    diagonals = good_diagonals(fp)
    selection = select_diagonals(fp, diagonals)
    completions = complete_cuts(fp, selection)
    return subdivide(fp, selection, completions)
