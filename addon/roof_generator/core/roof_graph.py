# SPDX-License-Identifier: GPL-3.0-or-later
"""Build an indexed planar roof graph from support-line constraints.

No polygon split, clipping, union or difference occurs here. Candidate creases
are bounded equal-height lines; domain transitions are support-line segments.
Visibility is interval subtraction, and face cycles follow ordered halfedges.
The graph stays in XY until its incident affine face constraints are embedded.
"""

from dataclasses import dataclass, replace
from functools import cmp_to_key, lru_cache
import itertools
import math
from .roof_geometry import EPS, GRID, UnsupportedRoofError, polygon_ring
from .roof_planes import RoofPlane, primitive
from .roof_parts import RoofPart

WELD = EPS * 4


@dataclass(frozen=True)
class GraphFace:
    outer: tuple[int, ...]
    holes: tuple[tuple[int, ...], ...]
    plane: RoofPlane
    part_ids: tuple[int, ...]


@dataclass(frozen=True)
class RoofGraph:
    vertices: tuple[tuple[float, float], ...]
    faces: tuple[GraphFace, ...]
    parts: tuple[RoofPart, ...]
    # Oriented edge follows the first incident face, with its interior on left.
    edges: tuple[tuple[int, int, int, int], ...]

    def embed(self):
        heights = [[] for _ in self.vertices]
        for face in self.faces:
            for loop in (face.outer, *face.holes):
                for i in loop:
                    heights[i].append(face.plane.height(self.vertices[i]))
        result = []
        for xy, values in zip(self.vertices, heights):
            if not values or max(values) - min(values) > EPS * 20:
                raise UnsupportedRoofError("incompatible roof height at graph junction")
            result.append((*xy, values[0]))
        return tuple(result)


@dataclass(frozen=True)
class Support:
    part: RoofPart
    planes: tuple[RoofPlane, ...]
    domain: tuple[tuple[float, float, float], ...]


def _value(plane, p):
    return plane[0] * p[0] + plane[1] * p[1] + plane[2]


def _difference(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _line(plane):
    a, b, c = plane
    size = math.hypot(a, b)
    if size <= GRID:
        return None
    return ((-a * c / size**2, -b * c / size**2), (-b / size, a / size))


def _bound(interval, point, direction, constraints):
    lo, hi = interval
    for plane in constraints:
        value = _value(plane, point)
        slope = plane[0] * direction[0] + plane[1] * direction[1]
        if abs(slope) <= GRID:
            if value < -GRID:
                return None
            continue
        root = -value / slope
        if slope > 0:
            lo = max(lo, root)
        else:
            hi = min(hi, root)
        if hi - lo <= EPS:
            return None
    return lo, hi


def _inside(p, ring):
    inside = False
    for a, b in zip(ring, ring[1:] + ring[:1]):
        if (a[1] > p[1]) != (b[1] > p[1]) and (
            p[0] < a[0] + (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1])
        ):
            inside = not inside
    return inside


def _footprint_intervals(point, direction, ring):
    projections = [
        (p[0] - point[0]) * direction[0] + (p[1] - point[1]) * direction[1]
        for p in ring
    ]
    events = [min(projections), max(projections)]
    dx, dy = direction
    for a, b in zip(ring, ring[1:] + ring[:1]):
        ex, ey = b[0] - a[0], b[1] - a[1]
        qx, qy = a[0] - point[0], a[1] - point[1]
        denominator = dx * ey - dy * ex
        if abs(denominator) <= GRID * math.hypot(ex, ey):
            if abs(qx * dy - qy * dx) <= GRID:
                events.extend(
                    (
                        (a[0] - point[0]) * dx + (a[1] - point[1]) * dy,
                        (b[0] - point[0]) * dx + (b[1] - point[1]) * dy,
                    )
                )
            continue
        t = (qx * ey - qy * ex) / denominator
        u = (qx * dy - qy * dx) / denominator
        if -GRID <= u <= 1 + GRID:
            events.append(t)
    events = sorted(events)
    return tuple(
        (lo, hi)
        for lo, hi in zip(events, events[1:])
        if hi - lo > EPS
        and _inside(
            (point[0] + (lo + hi) / 2 * dx, point[1] + (lo + hi) / 2 * dy), ring
        )
    )


def _subtract(intervals, removed):
    a, b = removed
    return tuple(
        piece
        for lo, hi in intervals
        for piece in (
            ((lo, min(hi, a)), (max(lo, b), hi)) if lo < b and a < hi else ((lo, hi),)
        )
        if piece[1] - piece[0] > EPS
    )


def _compare(first, second):
    for a, b in zip(first[:2], second[:2]):
        if abs(a - b) > EPS:
            return -1 if a < b else 1
    return (first[2] > second[2]) - (first[2] < second[2])


def _owner(point, inward, supports):
    choices = []
    for support in supports:
        if any(
            _value(c, point) < -EPS
            or (
                abs(_value(c, point)) <= EPS
                and c[0] * inward[0] + c[1] * inward[1] < -GRID
            )
            for c in support.domain
        ):
            continue
        slopes = [
            (
                _value(p.coefficients, point),
                p.coefficients[0] * inward[0] + p.coefficients[1] * inward[1],
                j,
            )
            for j, p in enumerate(support.planes)
        ]
        height, derivative, j = min(slopes, key=cmp_to_key(_compare))
        # On a coincident surface, earliest solid/plane owns the patch.
        choices.append((height, derivative, -support.part.id, j, support.planes[j]))
    if not choices:
        return None
    best = max(choices, key=cmp_to_key(_compare))
    return -best[2], best[4]


def _supports(parts):
    solids = tuple(primitive(part) for part in parts)
    planes, external = [], []
    for solid in solids:
        exterior = {source.part_edge for source in solid.part.source_edges}
        definitions = {
            p.key: p
            for p in solid.planes
            if p.source_edge is None or p.source_edge in exterior
        }
        planes.append(definitions)
        external.append(
            {p.key: p for p in definitions.values() if p.source_edge is not None}
        )
    changed = True
    while changed:
        changed = False
        for solid in solids:
            coords = tuple(solid.part.footprint.exterior.coords)[:-1]
            for neighbor in solid.part.neighbors:
                for key, plane in tuple(external[neighbor.part_id].items()):
                    if (
                        key not in external[solid.part.id]
                        and min(plane.height(p) - plane.eave_height for p in coords)
                        >= -EPS
                    ):
                        external[solid.part.id][key] = plane
                        planes[solid.part.id][key] = plane
                        changed = True
    result = []
    for solid in solids:
        part = solid.part
        if not planes[part.id]:
            raise UnsupportedRoofError(f"part {part.id} has no exterior roof support")
        definitions = tuple(planes[part.id][key] for key in sorted(planes[part.id]))
        constraints = tuple(
            source.support_line
            for source in sorted(
                {s.footprint_edge: s for s in part.source_edges}.values(),
                key=lambda s: s.footprint_edge,
            )
        )
        constraints += tuple(
            (
                p.coefficients[0],
                p.coefficients[1],
                p.coefficients[2] - part.parameters.eave_height,
            )
            for p in definitions
            if math.hypot(*p.coefficients[:2]) > GRID
        )
        result.append(
            Support(
                replace(
                    part, plane_definitions=tuple(p.coefficients for p in definitions)
                ),
                definitions,
                constraints,
            )
        )
    return tuple(result)


def _segments(supports, ring):
    segments = [(a, b, True) for a, b in zip(ring, ring[1:] + ring[:1])]
    references = [(s, p) for s in supports for p in s.planes]
    for (first, a), (second, b) in itertools.combinations(references, 2):
        if a.key == b.key:
            continue
        line = _line(_difference(a.coefficients, b.coefficients))
        if line is None:
            continue
        point, direction = line
        constraints = first.domain + second.domain
        constraints += tuple(
            _difference(p.coefficients, a.coefficients)
            for p in first.planes
            if p.key != a.key
        )
        constraints += tuple(
            _difference(p.coefficients, b.coefficients)
            for p in second.planes
            if p.key != b.key
        )
        intervals = tuple(
            piece
            for span in _footprint_intervals(point, direction, ring)
            if (piece := _bound(span, point, direction, constraints)) is not None
        )
        for support in supports:
            if not intervals:
                break
            # A min-envelope containing this same plane cannot be higher.
            if support.part.id in {first.part.id, second.part.id} or any(
                abs(_value(_difference(p.coefficients, a.coefficients), point)) <= GRID
                and abs(
                    (p.coefficients[0] - a.coefficients[0]) * direction[0]
                    + (p.coefficients[1] - a.coefficients[1]) * direction[1]
                )
                <= GRID
                for p in support.planes
            ):
                continue
            higher = support.domain + tuple(
                _difference(p.coefficients, a.coefficients) for p in support.planes
            )
            hidden = _bound(
                (intervals[0][0], intervals[-1][1]), point, direction, higher
            )
            if hidden is not None:
                intervals = _subtract(intervals, hidden)
        segments.extend(
            (
                (point[0] + lo * direction[0], point[1] + lo * direction[1]),
                (point[0] + hi * direction[0], point[1] + hi * direction[1]),
                False,
            )
            for lo, hi in intervals
        )
    # Domain transitions can terminate a roof or expose an unsupported height
    # step. Include their graph edges, then test the two incident face heights.
    for support in supports:
        for i, constraint in enumerate(support.domain):
            line = _line(constraint)
            if line is None:
                continue
            point, direction = line
            constraints = support.domain[:i] + support.domain[i + 1 :]
            for span in _footprint_intervals(point, direction, ring):
                bounded = _bound(span, point, direction, constraints)
                if bounded is not None:
                    lo, hi = bounded
                    segments.append(
                        (
                            (
                                point[0] + lo * direction[0],
                                point[1] + lo * direction[1],
                            ),
                            (
                                point[0] + hi * direction[0],
                                point[1] + hi * direction[1],
                            ),
                            False,
                        )
                    )
    return segments


def _node(segments):
    points = [[a, b] for a, b, _ in segments]
    for i, (a, b, _) in enumerate(segments):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        for j in range(i + 1, len(segments)):
            c, d, _ = segments[j]
            ex, ey = d[0] - c[0], d[1] - c[1]
            other_length = math.hypot(ex, ey)
            denominator = dx * ey - dy * ex
            qx, qy = c[0] - a[0], c[1] - a[1]
            if abs(denominator) <= WELD * min(length, other_length):
                if abs(dx * qy - dy * qx) <= WELD * length:
                    for k, u, v, candidates in ((i, a, b, (c, d)), (j, c, d, (a, b))):
                        for p in candidates:
                            t = (
                                (p[0] - u[0]) * (v[0] - u[0])
                                + (p[1] - u[1]) * (v[1] - u[1])
                            ) / math.dist(u, v) ** 2
                            if (
                                -WELD / math.dist(u, v)
                                <= t
                                <= 1 + WELD / math.dist(u, v)
                            ):
                                points[k].append(p)
                continue
            t = (qx * ey - qy * ex) / denominator
            u = (qx * dy - qy * dx) / denominator
            if (
                -WELD / length <= t <= 1 + WELD / length
                and -WELD / other_length <= u <= 1 + WELD / other_length
            ):
                point = (a[0] + t * dx, a[1] + t * dy)
                points[i].append(point)
                points[j].append(point)
    unique, buckets, indices = [], {}, {}
    for point in sorted(set(p for group in points for p in group)):
        cell = (math.floor(point[0] / WELD), math.floor(point[1] / WELD))
        near = [
            j
            for dx, dy in itertools.product((-1, 0, 1), repeat=2)
            for j in buckets.get((cell[0] + dx, cell[1] + dy), ())
            if math.dist(point, unique[j]) <= WELD
        ]
        if near:
            indices[point] = min(near)
        else:
            indices[point] = len(unique)
            buckets.setdefault(cell, []).append(len(unique))
            unique.append(point)
    edges = {}
    for group, (a, b, boundary) in zip(points, segments):
        dx, dy = b[0] - a[0], b[1] - a[1]
        order = sorted(
            {indices[p] for p in group},
            key=lambda j: (unique[j][0] - a[0]) * dx + (unique[j][1] - a[1]) * dy,
        )
        for u, v in zip(order, order[1:]):
            if math.dist(unique[u], unique[v]) <= EPS:
                continue
            key = tuple(sorted((u, v)))
            if boundary or key not in edges:
                edges[key] = (u, v) if boundary else None
    return tuple(unique), edges


def build_graph(parts, footprint):
    # Validate requested parameters before using a geometry-only cache. A
    # common positive vertical scaling/translation leaves this XY graph fixed.
    for part in parts:
        primitive(part)
    scale = next(
        (p.parameters.pitch for p in parts if p.parameters.roof_type != "flat"), 1.0
    )
    origin = parts[0].parameters.eave_height
    normalized = tuple(
        replace(
            part,
            parameters=replace(
                part.parameters,
                pitch=(
                    part.parameters.pitch / scale
                    if part.parameters.roof_type != "flat"
                    else 1.0
                ),
                eave_height=(part.parameters.eave_height - origin) / scale,
                planes=tuple(
                    (a / scale, b / scale, (c - origin) / scale)
                    for a, b, c in part.parameters.planes
                ),
            ),
        )
        for part in parts
    )
    graph = _build_graph(normalized, footprint)

    def restore(plane):
        a, b, c = plane.coefficients
        return replace(
            plane,
            coefficients=(a * scale, b * scale, c * scale + origin),
            eave_height=plane.eave_height * scale + origin,
        )

    restored_parts = tuple(
        replace(
            part,
            parameters=parts[i].parameters,
            plane_definitions=tuple(
                (a * scale, b * scale, c * scale + origin)
                for a, b, c in part.plane_definitions
            ),
        )
        for i, part in enumerate(graph.parts)
    )
    return replace(
        graph,
        parts=restored_parts,
        faces=tuple(replace(face, plane=restore(face.plane)) for face in graph.faces),
    )


@lru_cache(maxsize=256)
def _build_graph(parts, footprint):
    supports = _supports(parts)
    vertices, candidates = _node(_segments(supports, polygon_ring(footprint)))
    directed, neighbors, unused = {}, {}, []
    for (u, v), boundary in sorted(candidates.items()):
        if boundary is not None:
            u, v = boundary
        a, b = vertices[u], vertices[v]
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        length = math.dist(a, b)
        normal = (-(b[1] - a[1]) / length, (b[0] - a[0]) / length)
        left = _owner(mid, normal, supports)
        right = (
            None
            if boundary is not None
            else _owner(mid, (-normal[0], -normal[1]), supports)
        )
        if left is None or (boundary is None and right is None):
            raise UnsupportedRoofError("roof graph has an uncovered domain transition")
        if right is not None and left[1].key == right[1].key:
            unused.append((mid, left, right))
            continue
        if (
            right is not None
            and abs(left[1].height(mid) - right[1].height(mid)) > EPS * 20
        ):
            raise UnsupportedRoofError(
                "incompatible roof height difference at connector"
            )
        directed[u, v], directed[v, u] = left, right
        neighbors.setdefault(u, []).append(v)
        neighbors.setdefault(v, []).append(u)
    for u, adjacent in neighbors.items():
        adjacent.sort(
            key=lambda v: math.atan2(
                vertices[v][1] - vertices[u][1], vertices[v][0] - vertices[u][0]
            )
        )
    visited, cycles = set(), []
    for start in sorted(directed):
        if start in visited:
            continue
        edge, loop, owners = start, [], []
        while edge not in visited:
            visited.add(edge)
            u, v = edge
            loop.append(u)
            owners.append(directed[edge])
            adjacent = neighbors[v]
            edge = (v, adjacent[(adjacent.index(u) - 1) % len(adjacent)])
        if edge != start or len(set(loop)) != len(loop):
            raise UnsupportedRoofError("roof graph contains an invalid face cycle")
        if all(owner is None for owner in owners):
            continue
        keys = {owner[1].key for owner in owners if owner is not None}
        if any(owner is None for owner in owners) or len(keys) != 1:
            raise UnsupportedRoofError(
                "roof graph face has inconsistent support constraints"
            )
        ring = tuple(vertices[i] for i in loop)
        area = (
            sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(ring, ring[1:] + ring[:1]))
            / 2
        )
        if abs(area) <= EPS**2:
            raise UnsupportedRoofError("roof graph contains a zero-area face")
        plane = min(owners, key=lambda o: o[0])[1]
        cycles.append((tuple(loop), area, plane, {o[0] for o in owners}))
    faces = []
    for loop, area, plane, contributors in cycles:
        if area <= 0:
            continue
        outer = tuple(vertices[i] for i in loop)
        holes = tuple(
            hole
            for hole, signed, p, _ in cycles
            if signed < 0 and p.key == plane.key and _inside(vertices[hole[0]], outer)
        )
        for point, left, right in unused:
            if (
                left[1].key == plane.key
                and _inside(point, outer)
                and not any(
                    _inside(point, tuple(vertices[i] for i in hole)) for hole in holes
                )
            ):
                contributors.update((left[0], right[0]))
        faces.append(GraphFace(loop, holes, plane, tuple(sorted(contributors))))
    # Remove degree-two straight waypoints from every incident cycle together.
    # Junctions remain shared nodes and are never removed by face-local cleanup.
    adjacent = {}
    for face in faces:
        for loop in (face.outer, *face.holes):
            for a, b in zip(loop, loop[1:] + loop[:1]):
                adjacent.setdefault(a, set()).add(b)
                adjacent.setdefault(b, set()).add(a)
    removable = set()
    for v, neighbors in adjacent.items():
        if len(neighbors) != 2:
            continue
        a, b = (vertices[i] for i in sorted(neighbors))
        point = vertices[v]
        dx, dy = b[0] - a[0], b[1] - a[1]
        size = math.hypot(dx, dy)
        if size > WELD:
            t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / size**2
            if (
                0 < t < 1
                and abs(dx * (point[1] - a[1]) - dy * (point[0] - a[0])) <= WELD * size
            ):
                removable.add(v)
    faces = [
        replace(
            face,
            outer=tuple(v for v in face.outer if v not in removable),
            holes=tuple(
                tuple(v for v in hole if v not in removable) for hole in face.holes
            ),
        )
        for face in faces
    ]
    # Discard construction nodes on eliminated coplanar edges.
    used = sorted(
        {v for face in faces for loop in (face.outer, *face.holes) for v in loop}
    )
    mapping = {v: i for i, v in enumerate(used)}
    faces = tuple(
        replace(
            face,
            outer=tuple(mapping[v] for v in face.outer),
            holes=tuple(tuple(mapping[v] for v in hole) for hole in face.holes),
        )
        for face in faces
    )
    face_edges = {}
    for i, face in enumerate(faces):
        for loop in (face.outer, *face.holes):
            for a, b in zip(loop, loop[1:] + loop[:1]):
                face_edges.setdefault(tuple(sorted((a, b))), []).append((i, a, b))
    edges = tuple(
        (items[0][1], items[0][2], items[0][0], items[1][0] if len(items) == 2 else -1)
        for _, items in sorted(face_edges.items())
    )
    return RoofGraph(
        tuple(vertices[v] for v in used), faces, tuple(s.part for s in supports), edges
    )
