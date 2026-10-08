# SPDX-License-Identifier: GPL-3.0-or-later
"""SGA21-compatible geometry problem and analytic rectangle embedding."""

from dataclasses import dataclass
from collections import defaultdict
import math
from .graph import RoofGraph
from .errors import UnsupportedRoofError
from .footprint import EPS, sub, rectangle, area, inside, on_segment, cross, _intersects


from .mesh import RoofMesh


@dataclass(frozen=True)
class GeometryProblem:
    initial_vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, ...], ...]
    variable_xy: tuple[int, ...]
    variable_z: tuple[int, ...]
    fixed_z: tuple[tuple[int, float], ...]
    ridge_directions: tuple[tuple[tuple[int, int], tuple[float, float]], ...] = ()


def problem(graph, pitch=0.5, eave_height=0.0):
    """SGA21-ready variables and nonflat anchors; no topology/plane decisions."""
    if (
        not math.isfinite(pitch)
        or (graph.roof_type != "flat" and pitch <= 0)
        or not math.isfinite(eave_height)
    ):
        raise UnsupportedRoofError("positive finite pitch and finite eave required")
    if graph.roof_type == "shed":
        vertices = solve_analytic(graph, pitch, eave_height).vertices
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
    directions = []
    for edge in graph.edges:
        if edge.kind == "ridge":
            eave = graph.faces[edge.faces[0]].eaves[0]
            vector = sub(
                graph.outline[(eave + 1) % len(graph.outline)], graph.outline[eave]
            )
            size = math.hypot(*vector)
            directions.append((edge.vertices, tuple(v / size for v in vector)))
    return GeometryProblem(
        seeds,
        tuple(f.loop for f in graph.faces),
        tuple(i for i, v in enumerate(graph.vertices) if v.boundary is None),
        tuple(i for i in range(len(graph.vertices)) if i not in heights),
        tuple(sorted(heights.items())),
        tuple(directions),
    )


def rectangle_vertices(graph, pitch=0.5, eave_height=0.0):
    """Exact rectangle geometry, consuming already selected connectivity."""
    if not rectangle(graph.outline) or any(f.cells != (0,) for f in graph.faces):
        raise UnsupportedRoofError(
            "analytic solve supports one rectangle only; compound pitched embedding is not implemented"
        )
    if (
        not math.isfinite(pitch)
        or (graph.roof_type != "flat" and pitch <= 0)
        or not math.isfinite(eave_height)
    ):
        raise UnsupportedRoofError("invalid roof geometry parameters")
    result = [(*v.seed, eave_height) for v in graph.vertices]
    if graph.roof_type == "flat":
        return tuple(result)
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
    return tuple(result)


def solve_analytic(graph, pitch=0.5, eave_height=0.0):
    """Fixed graph embedding: flat surface or one rectangle, no topology edits."""
    if graph.roof_type == "flat":
        if not math.isfinite(eave_height):
            raise UnsupportedRoofError("finite eave height required")
        return RoofMesh(graph, tuple((*v.seed, eave_height) for v in graph.vertices))
    return RoofMesh(graph, rectangle_vertices(graph, pitch, eave_height))
