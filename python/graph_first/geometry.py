# SPDX-License-Identifier: GPL-3.0-or-later
"""Geometry owns disposable initialization and embedding of fixed face cycles."""

from dataclasses import dataclass
from collections import defaultdict
import math
from .graph import RoofGraph, UnsupportedGraphError
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


def ridge_seeds(outline, seeds, faces, locations, semantics):
    """Laplacian initialization constrained to declared primitive ridge axes.

    Unconstrained harmonic embedding is not safe for a concave fixed boundary.
    Connectivity and all edge meanings are inputs, never initializer outputs.
    """
    adjacent = defaultdict(set)
    incidence = defaultdict(list)
    for fi, face in enumerate(faces):
        for a, b in zip(face.loop, face.loop[1:] + face.loop[:1]):
            adjacent[a].add(b)
            adjacent[b].add(a)
            incidence[tuple(sorted((a, b)))].append(fi)
    axes = defaultdict(list)
    for edge, kind in semantics.items():
        if kind != "ridge":
            continue
        cap = next((v for v in edge if v in locations), None)
        if cap is None:
            raise UnsupportedGraphError("initial ridge axis needs a boundary port")
        joint = next(v for v in edge if v != cap)
        face = faces[incidence[edge][0]]
        eave = face.eaves[0]
        direction = sub(outline[(eave + 1) % len(outline)], outline[eave])
        size = math.hypot(*direction)
        axes[joint].append((seeds[cap], tuple(v / size for v in direction)))
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
                raise UnsupportedGraphError(
                    "coincident ridge axes need another initializer"
                )
            t = ((b[0] - a[0]) * e[1] - (b[1] - a[1]) * e[0]) / det
            result[vertex] = (a[0] + t * d[0], a[1] + t * d[1])
        else:
            raise UnsupportedGraphError("junction lacks one or two declared ridge axes")
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
            raise UnsupportedGraphError("singular ridge initialization")
        rows[i] = [v / value for v in rows[i]]
        for j in range(len(rows)):
            if j != i:
                value = rows[j][i]
                rows[j] = [a - value * b for a, b in zip(rows[j], rows[i])]
    for vertex, row in zip(variables, rows):
        p, d = lines[vertex]
        result[vertex] = tuple(p[k] + row[-1] * d[k] for k in (0, 1))
    if not _valid_drawing(outline, result, faces, locations, semantics):
        # Backtrack only disposable XY, towards the two declared ridge axes'
        # common point. That coincident limit is never emitted. This keeps the
        # graph, both axes and boundary fixed while finding a noncrossing seed.
        if len(lines) != 2:
            raise UnsupportedGraphError("ridge initializer has no interior drawing")
        (p, d), (q, e) = lines.values()
        det = cross(d, e)
        if abs(det) < 1e-8:
            raise UnsupportedGraphError("ridge initializer axes are parallel")
        t = cross(sub(q, p), e) / det
        common = tuple(p[k] + t * d[k] for k in (0, 1))
        original = tuple(result)
        fraction = 1.0
        while fraction > EPS:
            fraction /= 2
            for vertex in variables:
                result[vertex] = tuple(
                    common[k] + fraction * (original[vertex][k] - common[k])
                    for k in (0, 1)
                )
            if _valid_drawing(outline, result, faces, locations, semantics):
                break
        else:
            raise UnsupportedGraphError("no nondegenerate interior ridge initializer")
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
        raise UnsupportedGraphError("middle-junction initializer has no valid drawing")
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
    ridge_directions: tuple[tuple[tuple[int, int], tuple[float, float]], ...] = ()


@dataclass(frozen=True)
class Mesh:
    graph: RoofGraph
    vertices: tuple[tuple[float, float, float], ...]

    def __post_init__(self):
        if len(self.vertices) != len(self.graph.vertices) or any(
            len(p) != 3 or not all(math.isfinite(v) for v in p) for p in self.vertices
        ):
            raise UnsupportedGraphError(
                "mesh coordinates violate graph vertex contract"
            )
        for i, p in enumerate(self.vertices):
            if (
                self.graph.vertices[i].boundary is not None
                and math.dist(p[:2], self.graph.vertices[i].seed) > EPS * 20
            ):
                raise UnsupportedGraphError("mesh moves fixed footprint boundary")
            if any(math.dist(p, q) <= EPS for q in self.vertices[:i]):
                raise UnsupportedGraphError("mesh has coincident graph vertices")
        if not _valid_drawing(
            self.graph.outline,
            tuple(p[:2] for p in self.vertices),
            self.graph.faces,
            {i for i, v in enumerate(self.graph.vertices) if v.boundary is not None},
            {e.vertices: e.kind for e in self.graph.edges},
        ):
            raise UnsupportedGraphError("mesh has an invalid footprint projection")
        for face in self.graph.faces:
            points = tuple(self.vertices[i] for i in face.loop)
            if area(tuple(p[:2] for p in points)) <= EPS**2:
                raise UnsupportedGraphError("mesh face has nonpositive projection")
            a = tuple(points[1][k] - points[0][k] for k in range(3))
            normal = None
            for point in points[2:]:
                b = tuple(point[k] - points[0][k] for k in range(3))
                candidate = (
                    a[1] * b[2] - a[2] * b[1],
                    a[2] * b[0] - a[0] * b[2],
                    a[0] * b[1] - a[1] * b[0],
                )
                size = math.sqrt(sum(v * v for v in candidate))
                if size > EPS**2:
                    normal = tuple(v / size for v in candidate)
                    break
            if (
                normal is None
                or normal[2] <= 0
                or any(
                    abs(sum((p[k] - points[0][k]) * normal[k] for k in range(3)))
                    > EPS * 20
                    for p in points
                )
            ):
                raise UnsupportedGraphError(
                    "mesh face is nonplanar or has inconsistent normal"
                )

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
    if (
        not math.isfinite(pitch)
        or (graph.roof_type != "flat" and pitch <= 0)
        or not math.isfinite(eave_height)
    ):
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


def solve_rectangle(graph, pitch=0.5, eave_height=0.0):
    return Mesh(graph, rectangle_vertices(graph, pitch, eave_height))
