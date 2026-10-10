# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit geometry constraints and fixed-topology analytic/nonlinear solve."""

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
    slope_constraints: tuple[
        tuple[int, tuple[float, float, float], tuple[float, float], float], ...
    ] = ()

    def __post_init__(self):
        n = len(self.initial_vertices)
        if not n or any(
            len(p) != 3 or not all(math.isfinite(x) for x in p)
            for p in self.initial_vertices
        ):
            raise UnsupportedRoofError("geometry problem needs finite XYZ")
        for indices in (
            self.variable_xy,
            self.variable_z,
            tuple(i for i, _ in self.fixed_z),
        ):
            if len(set(indices)) != len(indices) or any(
                not isinstance(i, int) or not 0 <= i < n for i in indices
            ):
                raise UnsupportedRoofError("invalid geometry variable indices")
        fixed = dict(self.fixed_z)
        if (
            set(fixed) & set(self.variable_z)
            or set(fixed) | set(self.variable_z) != set(range(n))
            or any(not math.isfinite(z) for z in fixed.values())
        ):
            raise UnsupportedRoofError(
                "geometry problem needs disjoint complete Z ownership"
            )
        if not self.faces or any(
            len(f) < 3 or len(set(f)) != len(f) or any(not 0 <= i < n for i in f)
            for f in self.faces
        ):
            raise UnsupportedRoofError("invalid fixed geometry face cycles")
        for edge, direction in self.ridge_directions:
            if (
                len(edge) != 2
                or any(not 0 <= i < n for i in edge)
                or edge[0] == edge[1]
                or len(direction) != 2
                or not all(math.isfinite(x) for x in direction)
                or abs(math.hypot(*direction) - 1) > 1e-8
            ):
                raise UnsupportedRoofError("invalid declared ridge direction")

        for face, origin, inward, pitch in self.slope_constraints:
            if (
                len(origin) != 3
                or not all(math.isfinite(x) for x in origin)
                or not 0 <= face < len(self.faces)
                or len(inward) != 2
                or not all(math.isfinite(v) for v in inward)
                or abs(math.hypot(*inward) - 1) > 1e-8
                or not math.isfinite(pitch)
                or pitch <= 0
            ):
                raise UnsupportedRoofError("invalid explicit roof slope constraint")


def _support(face):
    if face.support is not None:
        return face.support
    if not face.eaves:
        raise UnsupportedRoofError("pitched face lacks a declared eave support")
    return face.eaves[0]


def _eave_line(graph, face):
    edge = _support(face)
    a, b = graph.outline[edge], graph.outline[(edge + 1) % len(graph.outline)]
    vector = sub(b, a)
    length = math.hypot(*vector)
    for other in face.eaves:
        c, d = graph.outline[other], graph.outline[(other + 1) % len(graph.outline)]
        direction = sub(d, c)
        if (
            abs(cross(vector, direction)) > 1e-8 * length * math.hypot(*direction)
            or abs(cross(vector, sub(c, a))) > 4 * EPS * length
        ):
            raise UnsupportedRoofError(
                "pitched face eaves are not one collinear supporting line"
            )
    return a, vector


def problem(graph, pitch=0.5, eave_height=0.0):
    """SGA21-ready variables and nonflat anchors; no topology/plane decisions."""
    if (
        not math.isfinite(pitch)
        or (graph.roof_type != "flat" and pitch <= 0)
        or not math.isfinite(eave_height)
    ):
        raise UnsupportedRoofError("positive finite pitch and finite eave required")
    if graph.roof_type != "flat":
        for face in graph.faces:
            _eave_line(graph, face)
    if graph.roof_type == "shed":
        eave = graph.faces[0].eaves[0]
        a, b = graph.outline[eave], graph.outline[(eave + 1) % len(graph.outline)]
        vector = sub(b, a)
        length = math.hypot(*vector)
        inward = (-vector[1] / length, vector[0] / length)
        vertices = tuple(
            (
                *v.seed,
                eave_height
                + pitch * sum(x * y for x, y in zip(sub(v.seed, a), inward)),
            )
            for v in graph.vertices
        )
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
            if graph.roof_type == "gable" and v.boundary is not None:
                face = next(f for f in graph.faces if i in f.loop)
                eave = _support(face)
                a, b = (
                    graph.outline[eave],
                    graph.outline[(eave + 1) % len(graph.outline)],
                )
                vector = sub(b, a)
                distance = cross(vector, sub(v.seed, a)) / math.hypot(*vector)
                heights[i] = eave_height + pitch * distance
            else:
                heights[i] = eave_height + pitch * width / 2
    for edge in graph.edges:
        if (
            edge.kind != "ridge"
            or any(graph.vertices[v].boundary is not None for v in edge.vertices)
            or all(v in heights for v in edge.vertices)
        ):
            continue
        # A receiver with both end caps consumed has no exterior height anchor.
        # Its declared opposite eaves fix the equal-pitch ridge rise to p*w/2.
        # This supplies solve constraints; it changes no topology or final XY.
        first, second = (graph.faces[f] for f in edge.faces)
        if first.cells != second.cells:
            raise UnsupportedRoofError(
                "interior ridge lacks one declared receiving eave on each slope"
            )
        a, b = (graph.outline[_support(f)] for f in (first, second))
        directions = tuple(
            sub(graph.outline[(_support(f) + 1) % len(graph.outline)], origin)
            for f, origin in ((first, a), (second, b))
        )
        size = math.hypot(*directions[0])
        if abs(cross(*directions)) > 1e-8 * size * math.hypot(*directions[1]):
            # Nonparallel declared planes give a sloping intersection, not a
            # constant-width height anchor. Leave Z to those actual equations.
            continue
        width = abs(cross(sub(b, a), directions[0])) / size
        if width <= EPS:
            raise UnsupportedRoofError("interior ridge has coincident receiving eaves")
        height = eave_height + pitch * width / 2
        for v in edge.vertices:
            if v in heights and abs(heights[v] - height) > 4 * EPS:
                raise UnsupportedRoofError("interior ridge height anchors conflict")
            heights[v] = height
    if (
        graph.roof_type == "gable"
        and not rectangle(graph.outline)
        and len(graph.outline) == 4
    ):
        # One nonflat anchor suffices; the second cap height is a solve variable.
        caps = sorted(i for i, v in enumerate(graph.vertices) if v.role == "ridge_end")
        heights.pop(caps[-1])
    interior_height = max(heights.values()) if heights else eave_height
    seeds = tuple(
        (*v.seed, heights.get(i, interior_height)) for i, v in enumerate(graph.vertices)
    )
    directions = []
    for edge in graph.edges:
        if edge.kind == "ridge":
            eave = _support(graph.faces[edge.faces[0]])
            if not rectangle(graph.outline) and len(graph.outline) == 4:
                vector = sub(
                    graph.vertices[edge.vertices[1]].seed,
                    graph.vertices[edge.vertices[0]].seed,
                )
            else:
                vector = sub(
                    graph.outline[(eave + 1) % len(graph.outline)], graph.outline[eave]
                )
                other=_support(graph.faces[edge.faces[1]])
                other_vector=sub(graph.outline[(other+1)%len(graph.outline)],graph.outline[other])
                if abs(cross(vector,other_vector))>1e-8*math.hypot(*vector)*math.hypot(*other_vector):
                    # Projected equal-height locus of the two real pitch planes.
                    first=(-vector[1]/math.hypot(*vector),vector[0]/math.hypot(*vector))
                    second=(-other_vector[1]/math.hypot(*other_vector),other_vector[0]/math.hypot(*other_vector))
                    actual=(-(first[1]-second[1]),first[0]-second[0])
                    if sum(a*b for a,b in zip(actual,vector))<0:actual=tuple(-x for x in actual)
                    vector=actual
            size = math.hypot(*vector)
            directions.append((edge.vertices, tuple(v / size for v in vector)))
    slopes = []
    if graph.roof_type != "flat":
        for fi, face in enumerate(graph.faces):
            eave = _support(face)
            direction = sub(
                graph.outline[(eave + 1) % len(graph.outline)], graph.outline[eave]
            )
            length = math.hypot(*direction)
            slopes.append(
                (
                    fi,
                    (*graph.outline[eave], eave_height),
                    (-direction[1] / length, direction[0] / length),
                    pitch,
                )
            )
    return GeometryProblem(
        seeds,
        tuple(f.loop for f in graph.faces),
        tuple(i for i, v in enumerate(graph.vertices) if v.boundary is None),
        tuple(i for i in range(len(graph.vertices)) if i not in heights),
        tuple(sorted(heights.items())),
        tuple(directions),
        tuple(slopes),
    )


def rectangle_vertices(graph, pitch=0.5, eave_height=0.0):
    """Exact rectangle geometry, consuming already selected connectivity."""
    if not rectangle(graph.outline) or any(f.cells != (0,) for f in graph.faces):
        raise UnsupportedRoofError("exact primitive embedding requires one rectangle")
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


def embed(graph, geometry):
    """Solve coordinates only, leaving surface validation to RoofMesh."""
    if geometry.faces != tuple(f.loop for f in graph.faces):
        raise UnsupportedRoofError("solve problem changes roof incidence")
    if graph.roof_type == "flat" or (
        graph.roof_type in {"shed", "gable"} and rectangle(graph.outline)
        and all(f.cells == (0,) for f in graph.faces)
    ):
        # The already anchored primitive has an exact embedding. The pitch is
        # read from its explicit height constraints, not selected by the solver.
        return geometry.initial_vertices
    from .constraints import has_fixed_planes
    if has_fixed_planes(geometry):
        from .plane_embedding import embed_planes
        return embed_planes(geometry)
    from .optimization import optimize

    embedding = optimize(geometry)
    return embedding.vertices


def solve(graph, geometry):
    """Consume one GeometryProblem and graph; never choose topology or retry."""
    return RoofMesh(graph, embed(graph, geometry))
