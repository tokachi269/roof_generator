# SPDX-License-Identifier: GPL-3.0-or-later
"""Classical good-diagonal minimum rectangular partition; no roof decisions."""

from dataclasses import dataclass
from collections import deque
import math
from .footprint import EPS, inside, on_segment, ray_hit, _intersects
from .graph import UnsupportedGraphError


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
        raise UnsupportedGraphError(
            "rectangle partition requires an orthogonal outline"
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
            a, b = fp.vertices[start], fp.vertices[end]
            if not inside(tuple((x + y) / 2 for x, y in zip(a, b)), fp.vertices):
                continue
            if any(
                on_segment(p, a, b)
                for i, p in enumerate(fp.vertices)
                if i not in (start, end)
            ):
                continue
            if any(
                _intersects(a, b, c, d)
                for i, (c, d) in enumerate(
                    zip(fp.vertices, fp.vertices[1:] + fp.vertices[:1])
                )
                if i not in (start, end)
                and (i + 1) % len(fp.vertices) not in (start, end)
            ):
                continue
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
            raise UnsupportedGraphError("conflict graph is not bipartite")
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
        raise UnsupportedGraphError(
            "matching does not certify a maximum independent set"
        )
    return selected


def select_diagonals(fp, diagonals):
    left = tuple(i for i, d in enumerate(diagonals) if d.axis == 0)
    right = tuple(i for i, d in enumerate(diagonals) if d.axis == 1)
    conflicts = []
    for i, a in enumerate(diagonals):
        for j, b in enumerate(diagonals[:i]):
            if not _intersects(*(fp.vertices[k] for k in a.endpoints + b.endpoints)):
                continue
            if a.axis == b.axis:
                raise UnsupportedGraphError(
                    "same-axis diagonals intersect: invalid open-interior chord"
                )
            conflicts.append((j, i) if b.axis == 0 else (i, j))
    conflicts = tuple(sorted(conflicts))
    matching = maximum_matching(left, right, conflicts)
    selected = independent_set(left, right, conflicts, matching)
    return Selection(diagonals, conflicts, matching, selected)
