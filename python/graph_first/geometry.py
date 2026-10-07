# SPDX-License-Identifier: GPL-3.0-or-later
"""Geometry owns disposable initialization and embedding of fixed face cycles."""

from dataclasses import dataclass
from collections import defaultdict
import math
from .graph import UnsupportedGraphError
from .footprint import sub, rectangle


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
            raise UnsupportedGraphError("disconnected harmonic initialization")
        rows[i] = [v / value for v in rows[i]]
        for j in range(len(rows)):
            if j != i:
                value = rows[j][i]
                rows[j] = [a - value * b for a, b in zip(rows[j], rows[i])]
    result = list(seeds)
    for v, row in zip(variables, rows):
        result[v] = tuple(row[-2:])
    return tuple(result)


@dataclass(frozen=True)
class GeometryProblem:
    initial_vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, ...], ...]
    variable_xy: tuple[int, ...]
    variable_z: tuple[int, ...]
    fixed_z: tuple[tuple[int, float], ...]


@dataclass(frozen=True)
class Mesh:
    graph: object
    vertices: tuple[tuple[float, float, float], ...]

    @property
    def faces(self):
        return tuple(f.loop for f in self.graph.faces)

    @property
    def face_parts(self):
        return tuple(f.cells for f in self.graph.faces)

    @property
    def edge_features(self):
        return {e.vertices: e.kind for e in self.graph.edges}


def problem(graph, pitch=0.5, eave_height=0.0):
    """SGA21-ready variables and nonflat anchors; no topology/plane decisions."""
    if not math.isfinite(pitch) or pitch <= 0 or not math.isfinite(eave_height):
        raise UnsupportedGraphError("positive finite pitch and finite eave required")
    if graph.roof_type == "shed":
        vertices = solve_rectangle(graph, pitch, eave_height).vertices
        return GeometryProblem(
            vertices,
            tuple(f.loop for f in graph.faces),
            (),
            (),
            tuple((i, p[2]) for i, p in enumerate(vertices)),
        )
    lengths = [
        math.dist(a, b)
        for a, b in zip(graph.outline, graph.outline[1:] + graph.outline[:1])
    ]
    heights = {}
    for i, v in enumerate(graph.vertices):
        if v.role == "corner" or graph.roof_type == "flat":
            heights[i] = eave_height
        elif v.role == "ridge_end":
            width = lengths[v.boundary.edge] if v.boundary is not None else min(lengths)
            heights[i] = eave_height + pitch * width / 2
    interior_height = max(heights.values()) if heights else eave_height
    seeds = tuple(
        (*v.seed, heights.get(i, interior_height)) for i, v in enumerate(graph.vertices)
    )
    return GeometryProblem(
        seeds,
        tuple(f.loop for f in graph.faces),
        tuple(i for i, v in enumerate(graph.vertices) if v.boundary is None),
        tuple(i for i in range(len(graph.vertices)) if i not in heights),
        tuple(sorted(heights.items())),
    )


def solve_rectangle(graph, pitch=0.5, eave_height=0.0):
    """Exact rectangle geometry, consuming already selected connectivity."""
    if not rectangle(graph.outline) or any(f.cells != (0,) for f in graph.faces):
        raise UnsupportedGraphError(
            "analytic solve supports one rectangle only; L awaits nonlinear solve"
        )
    if (
        not math.isfinite(pitch)
        or (graph.roof_type != "flat" and pitch <= 0)
        or not math.isfinite(eave_height)
    ):
        raise UnsupportedGraphError("invalid roof geometry parameters")
    result = [(*v.seed, eave_height) for v in graph.vertices]
    if graph.roof_type == "flat":
        return Mesh(graph, tuple(result))
    base = graph.faces[0].eaves[0]
    a = graph.outline[base]
    b = graph.outline[(base + 1) % 4]
    edge = sub(b, a)
    length = math.hypot(*edge)
    inward = (-edge[1] / length, edge[0] / length)
    if graph.roof_type == "shed":
        result = [
            (
                *v.seed,
                eave_height
                + pitch * sum(x * y for x, y in zip(sub(v.seed, a), inward)),
            )
            for v in graph.vertices
        ]
    else:
        width = min(
            math.dist(x, y)
            for x, y in zip(graph.outline, graph.outline[1:] + graph.outline[:1])
        )
        height = eave_height + pitch * width / 2
        for i, v in enumerate(graph.vertices):
            if v.role != "ridge_end":
                continue
            xy = v.seed
            if v.boundary is None:
                hips = [e for e in graph.edges if e.kind == "hip" and i in e.vertices]
                corners = [next(j for j in e.vertices if j != i) for e in hips]
                if len(corners) == 4:
                    xy = tuple(sum(p[k] for p in graph.outline) / 4 for k in range(2))
                else:
                    c, d = (graph.vertices[j].seed for j in corners)
                    midpoint = ((c[0] + d[0]) / 2, (c[1] + d[1]) / 2)
                    centre = tuple(
                        sum(p[k] for p in graph.outline) / 4 for k in range(2)
                    )
                    direction = sub(centre, midpoint)
                    size = math.hypot(*direction)
                    xy = tuple(
                        midpoint[k] + direction[k] / size * width / 2 for k in range(2)
                    )
            result[i] = (*xy, height)
    return Mesh(graph, tuple(result))
