# SPDX-License-Identifier: GPL-3.0-or-later
"""Test-only connected unit-cell outlines; never a production partition backend."""

import random


def outline(cells):
    edges = set()
    for x, y in sorted(cells):
        ring = ((x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1))
        for a, b in zip(ring, ring[1:] + ring[:1]):
            if (b, a) in edges:
                edges.remove((b, a))
            else:
                edges.add((a, b))
    following = {}
    for a, b in sorted(edges):
        if a in following:
            raise ValueError("point-touching grid outline")
        following[a] = b
    if not following:
        raise ValueError("empty grid outline")
    start = min(following)
    p = start
    ring = []
    while p not in ring:
        ring.append(p)
        p = following[p]
    if p != start or len(ring) != len(edges):
        raise ValueError("hole or disconnected grid outline")
    result = []
    for i, b in enumerate(ring):
        a, c = ring[i - 1], ring[(i + 1) % len(ring)]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]):
            result.append(b)
    return tuple(result)


def comb(teeth):
    cells = {(x, 0) for x in range(2 * teeth + 1)}
    cells.update((x, y) for x in range(1, 2 * teeth, 2) for y in range(1, 4))
    return outline(cells)


def staircase(steps):
    return outline({(x, y) for x in range(steps) for y in range(x + 1)})


def generated(count=500, seed=92821):
    rng = random.Random(seed)
    seen = set()
    while len(seen) < count:
        cells = {(0, 0)}
        for _ in range(rng.randrange(8, 65)):
            frontier = sorted(
                {
                    (x + dx, y + dy)
                    for x, y in cells
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                }
                - cells
            )
            rng.shuffle(frontier)
            for candidate in frontier:
                try:
                    outline(cells | {candidate})
                except ValueError:
                    continue
                cells.add(candidate)
                break
        points = outline(cells)
        lo_x = min(x for x, y in points)
        lo_y = min(y for x, y in points)
        points = tuple((x - lo_x, y - lo_y) for x, y in points)
        if not 6 <= len(points) <= 40 or points in seen:
            continue
        seen.add(points)
        yield points


def named():
    zig = (
        {(x, 0) for x in range(4)}
        | {(3, y) for y in range(4)}
        | {(x, 3) for x in range(3, 7)}
        | {(6, y) for y in range(3, 7)}
    )
    indent = (
        {(x, y) for x in range(8) for y in range(6)}
        - {(x, y) for x in (2, 3) for y in (4, 5)}
        - {(x, y) for x in (5, 6) for y in (0, 1)}
    )
    return {
        "staircase": staircase(6),
        "comb": comb(4),
        "zig-zag": outline(zig),
        "multiple_indentation": outline(indent),
        "comb_40": comb(9),
        "staircase_20": staircase(9),
    }
