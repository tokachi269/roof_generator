# SPDX-License-Identifier: GPL-3.0-or-later
"""Noncrossing XY initialization after roof incidence is fixed."""

from dataclasses import dataclass
from collections import defaultdict
import math
from .graph import RoofGraph, UnsupportedRoofError
from .footprint import EPS, sub, rectangle, area, inside, on_segment, cross, _intersects


def _valid_drawing(outline, seeds, faces, locations, semantics):
    """Metric initialization guard; never selects graph incidence/semantics."""
    if any(
        math.dist(p, q) <= EPS for i, p in enumerate(seeds) for q in seeds[:i]
    ) or any(not inside(p, outline) for i, p in enumerate(seeds) if i not in locations):
        return False
    if any(area(tuple(seeds[i] for i in f.loop)) <= EPS**2 for f in faces):
        return False
    edges = tuple(semantics)
    for index, (a, b) in enumerate(edges):
        for c, d in edges[:index]:
            shared = {a, b}.intersection((c, d))
            if not shared:
                if _intersects(seeds[a], seeds[b], seeds[c], seeds[d]):
                    return False
            else:
                # A shared endpoint is legal; overlapping spokes are not.
                if any(
                    on_segment(seeds[v], seeds[a], seeds[b])
                    for v in (c, d)
                    if v not in shared
                ) or any(
                    on_segment(seeds[v], seeds[c], seeds[d])
                    for v in (a, b)
                    if v not in shared
                ):
                    return False
        if (a not in locations or b not in locations) and not inside(
            tuple((seeds[a][k] + seeds[b][k]) / 2 for k in (0, 1)), outline
        ):
            return False
    return True


def ridge_seeds(
    outline, seeds, faces, locations, semantics, *, declared_axes, patches=()
):
    """Laplacian initialization constrained to declared primitive ridge axes.

    Unconstrained harmonic embedding is not safe for a concave fixed boundary.
    Connectivity and all edge meanings are inputs, never initializer outputs.
    """
    adjacent = defaultdict(set)
    for face in faces:
        for a, b in zip(face.loop, face.loop[1:] + face.loop[:1]):
            adjacent[a].add(b)
            adjacent[b].add(a)
    # Axes come from declared primitive ports, including an interior-to-interior
    # receiver ridge. No boundary-port inference or metric semantics discovery.
    axes = declared_axes
    result = list(seeds)
    lines = {}
    for vertex in range(len(seeds)):
        if vertex in locations:
            continue
        constraints = axes[vertex]
        if len(constraints) == 1:
            lines[vertex] = constraints[0]
        elif len(constraints) == 2:
            (a, d), (b, e) = constraints
            det = d[0] * e[1] - d[1] * e[0]
            if abs(det) < 1e-8:
                raise UnsupportedRoofError(
                    "coincident ridge axes need another initializer"
                )
            t = ((b[0] - a[0]) * e[1] - (b[1] - a[1]) * e[0]) / det
            result[vertex] = (a[0] + t * d[0], a[1] + t * d[1])
        else:
            raise UnsupportedRoofError("junction lacks one or two declared ridge axes")
    variables = sorted(lines)
    lookup = {v: i for i, v in enumerate(variables)}
    rows = []
    for vertex in variables:
        p, d = lines[vertex]
        row = [0.0] * (len(variables) + 1)
        row[lookup[vertex]] = len(adjacent[vertex])
        for other in adjacent[vertex]:
            if other in lines:
                q, e = lines[other]
                row[lookup[other]] -= sum(a * b for a, b in zip(d, e))
            else:
                q = result[other]
            row[-1] += sum(a * b for a, b in zip(d, sub(q, p)))
        rows.append(row)
    for i in range(len(rows)):
        pivot = max(range(i, len(rows)), key=lambda j: abs(rows[j][i]))
        rows[i], rows[pivot] = rows[pivot], rows[i]
        value = rows[i][i]
        if abs(value) < 1e-12:
            raise UnsupportedRoofError("singular ridge initialization")
        rows[i] = [v / value for v in rows[i]]
        for j in range(len(rows)):
            if j != i:
                value = rows[j][i]
                rows[j] = [a - value * b for a, b in zip(rows[j], rows[i])]
    for vertex, row in zip(variables, rows):
        p, d = lines[vertex]
        result[vertex] = tuple(p[k] + row[-1] * d[k] for k in (0, 1))
    if not _valid_drawing(outline, result, faces, locations, semantics):
        # Backtrack only disposable XY, towards each local pair's declared ridge axes'
        # common point. That coincident limit is never emitted. This keeps the
        # graph, both axes and boundary fixed while finding a noncrossing seed.
        pairs = tuple(patches) or (tuple(lines),)
        if any(len(pair) != 2 for pair in pairs) or {
            v for pair in pairs for v in pair
        } != set(lines):
            raise UnsupportedRoofError(
                "ridge initializer has no independent local patches"
            )
        targets = {}
        for first, second in pairs:
            (p, d), (q, e) = lines[first], lines[second]
            det = cross(d, e)
            if abs(det) < 1e-8:
                raise UnsupportedRoofError("ridge initializer axes are parallel")
            t = cross(sub(q, p), e) / det
            common = tuple(p[k] + t * d[k] for k in (0, 1))
            targets[first] = targets[second] = common
        original = tuple(result)
        fraction = 1.0
        while fraction > EPS:
            fraction /= 2
            for vertex in variables:
                result[vertex] = tuple(
                    targets[vertex][k]
                    + fraction * (original[vertex][k] - targets[vertex][k])
                    for k in (0, 1)
                )
            if _valid_drawing(outline, result, faces, locations, semantics):
                break
        else:
            raise UnsupportedRoofError("no nondegenerate interior ridge initializer")
    return tuple(result)


def middle_seeds(outline, seeds, faces, locations, semantics, host_ports, slots):
    """Disposable drawing AFTER middle-attachment incidence is fixed.

    Project each opening midpoint onto the declared host ridge axis. Equal
    junctions lie on that axis; narrow junctions start inside the host slope
    strip. The half-strip point is an initialization choice, not a roof vertex
    discovered from a center or solved height/plane. No pitch/XYZ is used.
    """
    result = list(seeds)
    a, b = (seeds[i] for i in host_ports)
    direction = sub(b, a)
    size = sum(v * v for v in direction)
    for junction, first, second, equal in slots:
        opening = tuple((first[k] + second[k]) / 2 for k in (0, 1))
        t = sum(x * y for x, y in zip(sub(opening, a), direction)) / size
        axis = tuple(a[k] + t * direction[k] for k in (0, 1))
        result[junction] = (
            axis if equal else tuple((opening[k] + axis[k]) / 2 for k in (0, 1))
        )
    if not _valid_drawing(outline, result, faces, locations, semantics):
        raise UnsupportedRoofError("middle-junction initializer has no valid drawing")
    return tuple(result)


def harmonic_seeds(seeds, faces, fixed):
    """Tutte/Laplacian initialization, after all graph incidences are selected."""
    adjacent = defaultdict(set)
    for face in faces:
        for a, b in zip(face.loop, face.loop[1:] + face.loop[:1]):
            adjacent[a].add(b)
            adjacent[b].add(a)
    variables = [i for i in range(len(seeds)) if i not in fixed]
    if not variables:
        return tuple(seeds)
    lookup = {v: i for i, v in enumerate(variables)}
    rows = []
    for vertex in variables:
        row = [0.0] * (len(variables) + 2)
        row[lookup[vertex]] = len(adjacent[vertex])
        for other in adjacent[vertex]:
            if other in lookup:
                row[lookup[other]] -= 1
            else:
                row[-2] += seeds[other][0]
                row[-1] += seeds[other][1]
        rows.append(row)
    for i in range(len(rows)):
        pivot = max(range(i, len(rows)), key=lambda j: abs(rows[j][i]))
        rows[i], rows[pivot] = rows[pivot], rows[i]
        value = rows[i][i]
        if abs(value) < 1e-12:
            raise UnsupportedRoofError("disconnected harmonic initialization")
        rows[i] = [v / value for v in rows[i]]
        for j in range(len(rows)):
            if j != i:
                value = rows[j][i]
                rows[j] = [a - value * b for a, b in zip(rows[j], rows[i])]
    result = list(seeds)
    for v, row in zip(variables, rows):
        result[v] = tuple(row[-2:])
    return tuple(result)
