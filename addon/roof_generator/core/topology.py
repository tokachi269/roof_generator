# SPDX-License-Identifier: GPL-3.0-or-later
"""Primitive incidences and cell grafts decide topology without roof planes."""

import math
from dataclasses import dataclass, asdict
from collections import defaultdict
from .footprint import EPS, rectangle, on_segment, sub
from .provenance import BoundaryPoint
from .graph import RoofFace, RoofGraph, make_graph, boundary_span
from .errors import UnsupportedRoofError
from .initialization import harmonic_seeds, ridge_seeds, middle_seeds
from .junctions import plan


def _key(a, b):
    return tuple(sorted((a, b)))


def rectangle_graph(footprint, roof_type="gable", *, shed_edge=None):
    return _rectangle_graph(
        footprint.vertices, footprint.source_edges, roof_type, shed_edge=shed_edge
    )


def _rectangle_graph(
    outline, source_edges, roof_type, *, shed_edge=None, cell=0, ridge_axis=None
):
    if not rectangle(outline):
        raise UnsupportedRoofError("rectangle primitive requires a rectangle")
    if roof_type not in {"gable", "hip", "shed", "flat"}:
        raise UnsupportedRoofError("unsupported primitive type")
    lengths = [math.dist(a, b) for a, b in zip(outline, outline[1:] + outline[:1])]
    # Canonical cell-edge order, not the input's cyclic first vertex, resolves
    # equal-length choices. An explicit shed edge specifies directional intent.
    base = min(
        range(4),
        key=lambda i: (
            (
                sum(not source_edges[j] for j in (i, (i + 2) % 4))
                if roof_type in {"gable", "shed"}
                else 0
            ),
            -round(lengths[i], 10),
            tuple(
                sorted(
                    tuple(round(x, 10) for x in p)
                    for p in (outline[i], outline[(i + 1) % 4])
                )
            ),
        ),
    )
    if ridge_axis is not None:
        if ridge_axis not in (0, 1) or roof_type != "gable":
            raise UnsupportedRoofError("ridge_axis selects a gable member axis")
        base = next(
            i
            for i in range(4)
            if abs(outline[(i + 1) % 4][ridge_axis] - outline[i][ridge_axis]) > EPS
        )
    if shed_edge is not None:
        if (
            roof_type != "shed"
            or not isinstance(shed_edge, int)
            or not 0 <= shed_edge < 4
        ):
            raise UnsupportedRoofError(
                "shed_edge must select a rectangle boundary edge"
            )
        base = shed_edge
    v = tuple((base + i) % 4 for i in range(4))
    seeds = list(outline)
    locations = {i: BoundaryPoint(i, 0) for i in range(4)}
    roles = ["corner"] * 4
    semantics = {}
    if roof_type in {"flat", "shed"}:
        faces = (
            RoofFace(
                (0, 1, 2, 3),
                (cell,),
                tuple(range(4)) if roof_type == "flat" else (base,),
            ),
        )
        for i in range(4):
            semantics[_key(i, (i + 1) % 4)] = (
                "eave"
                if roof_type == "flat" or i in (base, (base + 2) % 4)
                else "gable_end"
            )
    elif roof_type == "hip" and abs(lengths[base] - lengths[(base + 1) % 4]) <= 1e-9:
        seeds.append((0, 0))
        roles.append("ridge_end")
        faces = tuple(RoofFace((i, (i + 1) % 4, 4), (cell,), (i,)) for i in range(4))
        for i in range(4):
            semantics[_key(i, (i + 1) % 4)] = "eave"
            semantics[_key(i, 4)] = "hip"
    else:
        seeds.extend(((0, 0), (0, 0)))
        roles.extend(("ridge_end", "ridge_end"))
        if roof_type == "gable":
            for vertex, edge in ((4, (base + 1) % 4), (5, (base + 3) % 4)):
                a, b = outline[edge], outline[(edge + 1) % 4]
                seeds[vertex] = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                locations[vertex] = BoundaryPoint(edge, 0.5)
            faces = (
                RoofFace((v[0], v[1], 4, 5), (cell,), (base,)),
                RoofFace((4, v[2], v[3], 5), (cell,), ((base + 2) % 4,)),
            )
            for a, b in ((v[0], v[1]), (v[2], v[3])):
                semantics[_key(a, b)] = "eave"
            for a, b in ((v[1], 4), (4, v[2]), (v[3], 5), (5, v[0])):
                semantics[_key(a, b)] = "gable_end"
        else:
            faces = (
                RoofFace((v[0], v[1], 4, 5), (cell,), (base,)),
                RoofFace((v[1], v[2], 4), (cell,), ((base + 1) % 4,)),
                RoofFace((v[2], v[3], 5, 4), (cell,), ((base + 2) % 4,)),
                RoofFace((v[3], v[0], 5), (cell,), ((base + 3) % 4,)),
            )
            for i in range(4):
                semantics[_key(i, (i + 1) % 4)] = "eave"
            for a, b in ((v[1], 4), (v[2], 4), (v[3], 5), (v[0], 5)):
                semantics[_key(a, b)] = "hip"
        semantics[4, 5] = "ridge"
    seeds = harmonic_seeds(seeds, faces, locations)
    return make_graph(
        outline,
        source_edges,
        seeds,
        locations,
        roles,
        faces,
        semantics,
        roof_type,
    )


@dataclass(frozen=True)
class RoofConnection:
    host: int
    branch: int
    shared: tuple[int, int]
    terminated_ports: tuple[int, ...]
    junctions: tuple[int, ...]
    wider_cell: int | None
    kind: str = "terminal"


@dataclass(frozen=True)
class Composition:
    graph: RoofGraph
    primitives: tuple[RoofGraph, ...]
    connections: tuple[RoofConnection, ...]

    def inspect(self):
        return {
            "graph": self.graph.inspect(),
            "primitives": [g.inspect() for g in self.primitives],
            "connections": [asdict(c) for c in self.connections],
        }


def cell_primitives(decomposition, roof_type="gable", *, axes=None):
    """Candidate primitive incidences; these are never a completed roof."""
    return tuple(
        _rectangle_graph(
            tuple(decomposition.vertices[i] for i in cell.corners),
            tuple(
                tuple(
                    sorted({i for span in side.exterior for i in span.original_edges})
                )
                for side in cell.sides
            ),
            roof_type,
            cell=cell.id,
            ridge_axis=None if axes is None else axes[cell.id],
        )
        for cell in decomposition.cells
    )


def compose(decomposition, roof_type="gable", *, axes=None, shed_edge=None):
    fp = decomposition.footprint
    if roof_type == "flat":
        # Flat has one coplanar exterior cycle. Neither artificial cuts nor
        # unresolved compound member axes can change its topology.
        graph = make_graph(
            fp.vertices,
            fp.source_edges,
            fp.vertices,
            {i: BoundaryPoint(i, 0) for i in range(len(fp.vertices))},
            ["corner"] * len(fp.vertices),
            (
                RoofFace(
                    tuple(range(len(fp.vertices))),
                    tuple(c.id for c in decomposition.cells),
                    tuple(range(len(fp.vertices))),
                ),
            ),
            {
                _key(i, (i + 1) % len(fp.vertices)): "eave"
                for i in range(len(fp.vertices))
            },
            "flat",
        )
        return Composition(graph, (), ())
    if len(decomposition.cells) == 1:
        g = _rectangle_graph(
            fp.vertices,
            fp.source_edges,
            roof_type,
            shed_edge=shed_edge,
            ridge_axis=None if axes is None or roof_type != "gable" else axes[0],
        )
        return Composition(g, (g,), ())
    if roof_type != "gable":
        raise UnsupportedRoofError(
            "multi-cell composition currently supports gable only"
        )
    primitives = cell_primitives(decomposition, axes=axes)
    relations = plan(decomposition, primitives)
    if any(r.kind == "terminal" for r in relations):
        return _terminals(decomposition, primitives, relations)
    return _middle(decomposition, primitives, relations)


def _middle(decomposition, primitives, relations):
    """Splice published narrow-branch extension / equal-width T incidence.

    All incidences and meanings are selected before drawing. Artificial cell
    edges and consumed branch caps never enter the final graph. Host ridge
    survives; only the equal-width T splits it and its attached slope cycle.
    """
    fp = decomposition.footprint
    host = relations[0].host
    seeds = list(fp.vertices)
    roles = ["corner"] * len(seeds)
    locations = {i: BoundaryPoint(i, 0) for i in range(len(seeds))}

    def boundary_port(cell, local):
        point = primitives[cell].vertices[local].seed
        edges = [
            i
            for i, a in enumerate(fp.vertices)
            if on_segment(point, a, fp.vertices[(i + 1) % len(fp.vertices)])
        ]
        if len(edges) != 1:
            raise UnsupportedRoofError(
                "surviving ridge port lacks a physical exterior edge"
            )
        edge = edges[0]
        axis = sub(fp.vertices[(edge + 1) % len(fp.vertices)], fp.vertices[edge])
        t = sum(x * y for x, y in zip(sub(point, fp.vertices[edge]), axis)) / sum(
            v * v for v in axis
        )
        vertex = len(seeds)
        locations[vertex] = BoundaryPoint(edge, t)
        seeds.append(point)
        roles.append("ridge_end")
        return vertex

    maps = {host: dict(enumerate(decomposition.cells[host].corners))}
    host_caps = tuple(
        i for i, v in enumerate(primitives[host].vertices) if v.role == "ridge_end"
    )
    for cap in host_caps:
        maps[host][cap] = boundary_port(host, cap)
    joints = {}
    shared_junction = None
    for relation in relations:
        branch, near = relation.branch, relation.branch_port
        far = next(
            i
            for i, v in enumerate(primitives[branch].vertices)
            if v.role == "ridge_end" and i != near
        )
        maps[branch] = dict(enumerate(decomposition.cells[branch].corners))
        maps[branch][far] = boundary_port(branch, far)
        if relation.equal_width and shared_junction is not None:
            junction = shared_junction
        else:
            junction = len(seeds)
            seeds.append((0, 0))
            roles.append("junction")
            if relation.equal_width:
                shared_junction = junction
        joints[branch] = junction
        maps[branch][near] = junction
    equal = list(dict.fromkeys(joints[r.branch] for r in relations if r.equal_width))
    side_relations = defaultdict(list)
    for relation in relations:
        side_relations[relation.host_side].append(relation)
    for side, items in side_relations.items():
        a, b = (
            decomposition.vertices[i]
            for i in decomposition.cells[host].sides[side].vertices
        )
        direction = sub(b, a)
        items.sort(
            key=lambda r: sum(
                x * y
                for x, y in zip(sub(decomposition.vertices[r.shared[0]], a), direction)
            )
        )
    meanings = {}
    host_ridge = tuple(maps[host][i] for i in host_caps)
    chain = (host_ridge[0], *equal, host_ridge[1])
    for a, b in zip(chain, chain[1:]):
        meanings[_key(a, b)] = "ridge"
    for relation in relations:
        branch = relation.branch
        junction = joints[branch]
        far = next(i for i in maps[branch] if i >= 4 and i != relation.branch_port)
        meanings[_key(junction, maps[branch][far])] = "ridge"
        for corner in relation.shared:
            meanings[_key(junction, corner)] = "valley"
    faces = []
    allowed_eaves = []
    for cell, primitive in enumerate(primitives):
        mapping = maps[cell]
        for face in primitive.faces:
            loop = []
            for a, b in zip(face.loop, face.loop[1:] + face.loop[:1]):
                loop.append(mapping[a])
                if cell == host:
                    if {a, b} == set(host_caps):
                        loop.extend(equal if a == host_caps[0] else reversed(equal))
                    if a < 4 and b == (a + 1) % 4:
                        for relation in side_relations[a]:
                            loop.extend(
                                (
                                    relation.shared[0],
                                    joints[relation.branch],
                                    relation.shared[1],
                                )
                            )
            cycles = [tuple(loop)]
            for junction in equal:
                if loop.count(junction) == 2:
                    i = loop.index(junction)
                    j = loop.index(junction, i + 1)
                    cycles = [tuple(loop[i:j]), tuple(loop[j:] + loop[:i])]
            eaves = {
                span.edge
                for side in face.eaves
                for span in decomposition.cells[cell].sides[side].exterior
            }
            for cycle in cycles:
                faces.append(RoofFace(cycle, (cell,), ()))
                allowed_eaves.append(eaves)
    incidence = defaultdict(list)
    for i, face in enumerate(faces):
        for a, b in zip(face.loop, face.loop[1:] + face.loop[:1]):
            incidence[_key(a, b)].append(i)
    actual_eaves = defaultdict(set)
    for (a, b), owners in incidence.items():
        if len(owners) != 1:
            continue
        span = boundary_span(fp.vertices, fp.source_edges, locations[a], locations[b])
        face = owners[0]
        meanings[a, b] = "eave" if span.edge in allowed_eaves[face] else "gable_end"
        if meanings[a, b] == "eave":
            actual_eaves[face].add(span.edge)
    faces = tuple(
        RoofFace(f.loop, f.cells, tuple(sorted(actual_eaves[i])))
        for i, f in enumerate(faces)
    )
    slots = tuple(
        (
            joints[r.branch],
            *(decomposition.vertices[i] for i in r.shared),
            r.equal_width,
        )
        for r in relations
    )
    seeds = middle_seeds(
        fp.vertices, seeds, faces, locations, meanings, host_ridge, slots
    )
    graph = make_graph(
        fp.vertices, fp.source_edges, seeds, locations, roles, faces, meanings, "gable"
    )
    connections = tuple(
        RoofConnection(
            r.host,
            r.branch,
            _key(*r.shared),
            (r.branch_port,),
            (joints[r.branch],),
            None if r.equal_width else r.host,
            "middle",
        )
        for r in relations
    )
    return Composition(graph, primitives, connections)


def _terminals(decomposition, primitives, relations):
    """Replace all distinct host-end corner ports simultaneously.

    Published branch extension/shared-corner incidence, restricted by plan().
    This rewrites the receiver's cycles once, not a sequence of pairwise roofs.
    Initial XY is assigned only after every incidence and semantic is fixed.
    """
    fp = decomposition.footprint
    host = relations[0].host
    hc = decomposition.cells[host]
    seeds = list(fp.vertices)
    roles = ["corner"] * len(seeds)
    locations = {i: BoundaryPoint(i, 0) for i in range(len(seeds))}
    consumed = {(host, r.host_port) for r in relations if r.host_port is not None} | {
        (r.branch, r.branch_port) for r in relations
    }
    ports = {}
    for ci, primitive in enumerate(primitives):
        for local, vertex in enumerate(primitive.vertices):
            if vertex.role != "ridge_end" or (ci, local) in consumed:
                continue
            p = vertex.seed
            candidates = [
                i
                for i, a in enumerate(fp.vertices)
                if on_segment(p, a, fp.vertices[(i + 1) % len(fp.vertices)])
            ]
            if len(candidates) != 1:
                raise UnsupportedRoofError(
                    "surviving gable port lacks one physical boundary"
                )
            edge = candidates[0]
            a = fp.vertices[edge]
            v = sub(fp.vertices[(edge + 1) % len(fp.vertices)], a)
            t = sum(x * y for x, y in zip(sub(p, a), v)) / sum(x * x for x in v)
            ports[ci, local] = len(seeds)
            locations[len(seeds)] = BoundaryPoint(edge, t)
            seeds.append(p)
            roles.append("ridge_end")
    patches = []
    declared_axes = defaultdict(list)
    corners = []
    middle_joints = {}
    for r in relations:
        if r.kind == "middle":
            joint = len(seeds)
            caps = [v.seed for v in primitives[host].vertices if v.role == "ridge_end"]
            direction = sub(caps[1], caps[0])
            size = sum(x * x for x in direction)
            opening = tuple(
                sum(decomposition.vertices[i][k] for i in r.shared) / 2 for k in (0, 1)
            )
            position = (
                sum(x * y for x, y in zip(sub(opening, caps[0]), direction)) / size
            )
            projected = tuple(caps[0][k] + position * direction[k] for k in (0, 1))
            seeds.append(tuple((opening[k] + projected[k]) / 2 for k in (0, 1)))
            roles.append("junction")
            ports[r.branch, r.branch_port] = joint
            middle_joints[r.branch] = joint
            caps = [
                v.seed for v in primitives[r.branch].vertices if v.role == "ridge_end"
            ]
            vector = sub(caps[1], caps[0])
            size = math.hypot(*vector)
            declared_axes[joint].append((caps[0], tuple(x / size for x in vector)))
            continue
        cut = next(iter(set(r.shared).intersection(hc.sides[r.host_side].vertices)))
        reflex = next(i for i in r.shared if i != cut)
        near_side = primitives[host].vertices[r.host_port].boundary.edge
        outer = next(i for i in hc.sides[near_side].vertices if i != cut)
        high = len(seeds)
        seeds.append((0, 0))
        roles.append("junction")
        low = high
        wider = None
        if not r.equal_width:
            low = len(seeds)
            seeds.append((0, 0))
            roles.append("junction")
            wider = host if r.host_width > r.branch_width else r.branch
            patches.append((high, low))
        host_joint = low if wider == r.branch else high
        branch_joint = low if wider == host else high
        # Start with shared-corner incidence; refine every unequal junction
        # together below, using original cycle neighbors rather than edit order.
        ports[host, r.host_port] = high
        ports[r.branch, r.branch_port] = high
        corners.append(
            (r, cut, reflex, outer, high, low, host_joint, branch_joint, wider)
        )
        for ci, joint in ((host, host_joint), (r.branch, branch_joint)):
            caps = [v.seed for v in primitives[ci].vertices if v.role == "ridge_end"]
            vector = sub(caps[1], caps[0])
            size = math.hypot(*vector)
            declared_axes[joint].append((caps[0], tuple(x / size for x in vector)))
    faces = []
    cuts = {cut for _, cut, *_ in corners}
    by_branch = {r.branch: (cut, outer) for r, cut, _, outer, *_ in corners}
    for ci, primitive in enumerate(primitives):
        cell = decomposition.cells[ci]
        mapping = dict(enumerate(cell.corners))
        mapping.update({local: v for (owner, local), v in ports.items() if owner == ci})
        for face in primitive.faces:
            loop = []
            for a, b in zip(face.loop, face.loop[1:] + face.loop[:1]):
                node = mapping[a]
                if ci == host and a < 4 and node in cuts:
                    pass
                elif ci in by_branch and a < 4 and node == by_branch[ci][0]:
                    loop.append(by_branch[ci][1])
                else:
                    loop.append(node)
                if ci == host and a < 4 and b < 4:
                    edge = {mapping[a], mapping[b]}
                    inserts = [
                        (r, reflex)
                        for r, _, reflex, *_ in corners
                        if edge == set(cell.sides[r.host_side].vertices)
                    ]
                    # At distinct ends of one side, order in that CCW side.
                    start = decomposition.vertices[mapping[a]]
                    paths = [
                        (decomposition.vertices[reflex], (reflex,))
                        for _, reflex in inserts
                    ]
                    paths.extend(
                        (
                            decomposition.vertices[r.shared[0]],
                            (r.shared[0], middle_joints[r.branch], r.shared[1]),
                        )
                        for r in relations
                        if r.kind == "middle"
                        and edge == set(cell.sides[r.host_side].vertices)
                    )
                    paths.sort(key=lambda pair: math.dist(start, pair[0]))
                    for _, path in paths:
                        loop.extend(path)
            eaves = tuple(
                sorted(
                    {
                        span.edge
                        for side in face.eaves
                        for span in cell.sides[side].exterior
                    }
                )
            )
            faces.append(RoofFace(tuple(loop), (ci,), eaves))
    refinement = {}
    for r, _, reflex, outer, high, low, hj, bj, _ in corners:
        if high == low:
            continue
        hother = next(
            ports[host, i]
            for i, v in enumerate(primitives[host].vertices)
            if v.role == "ridge_end" and i != r.host_port
        )
        bfar = next(
            ports[r.branch, i]
            for i, v in enumerate(primitives[r.branch].vertices)
            if v.role == "ridge_end" and i != r.branch_port
        )
        refinement[high] = {hother: hj, outer: high, bfar: bj, reflex: low}
    refined = []
    for face in faces:
        loop = []
        for i, v in enumerate(face.loop):
            if v not in refinement:
                loop.append(v)
                continue
            prev, nxt = face.loop[i - 1], face.loop[(i + 1) % len(face.loop)]
            groups = refinement[v]
            first, second = groups[prev], groups[nxt]
            loop.extend((first,) if first == second else (first, second))
        refined.append(RoofFace(tuple(loop), face.cells, face.eaves))
    faces = refined
    host_ends = {
        i: ports[host, i]
        for i, v in enumerate(primitives[host].vertices)
        if v.role == "ridge_end"
    }
    meanings = {}
    connections = []
    for r, _, reflex, outer, high, low, hj, bj, wider in corners:
        host_ends[r.host_port] = hj
        bfar = next(
            ports[r.branch, i]
            for i, v in enumerate(primitives[r.branch].vertices)
            if v.role == "ridge_end" and i != r.branch_port
        )
        meanings[_key(bj, bfar)] = "ridge"
        meanings[_key(high, outer)] = "hip"
        meanings[_key(low, reflex)] = "valley"
        if high != low:
            meanings[_key(high, low)] = "hip"
        connections.append(
            RoofConnection(
                host,
                r.branch,
                _key(*r.shared),
                (r.host_port, r.branch_port),
                (high,) if high == low else (high, low),
                wider,
            )
        )
    for r in relations:
        if r.kind != "middle":
            continue
        joint = middle_joints[r.branch]
        far = next(
            ports[r.branch, i]
            for i, v in enumerate(primitives[r.branch].vertices)
            if v.role == "ridge_end" and i != r.branch_port
        )
        meanings[_key(joint, far)] = "ridge"
        for corner in r.shared:
            meanings[_key(joint, corner)] = "valley"
        connections.append(
            RoofConnection(
                host,
                r.branch,
                _key(*r.shared),
                (r.branch_port,),
                (joint,),
                host,
                "middle",
            )
        )
    meanings[_key(*host_ends.values())] = "ridge"
    incidence = defaultdict(list)
    for i, face in enumerate(faces):
        for a, b in zip(face.loop, face.loop[1:] + face.loop[:1]):
            incidence[_key(a, b)].append(i)
    for (a, b), owners in incidence.items():
        if len(owners) == 1:
            span = boundary_span(
                fp.vertices, fp.source_edges, locations[a], locations[b]
            )
            meanings[a, b] = (
                "eave" if span.edge in faces[owners[0]].eaves else "gable_end"
            )
    seeds = ridge_seeds(
        fp.vertices,
        seeds,
        faces,
        locations,
        meanings,
        declared_axes=declared_axes,
        patches=patches,
        fixed_seeds=tuple(middle_joints.values()),
    )
    graph = make_graph(
        fp.vertices, fp.source_edges, seeds, locations, roles, faces, meanings, "gable"
    )
    return Composition(graph, primitives, tuple(connections))


def quadrilateral_graph(footprint, roof_type, *, eave=0):
    """Two equal-pitch slopes with boundary ports on the distance bisector."""
    outline = footprint.vertices
    if len(outline) != 4 or footprint.reflex or roof_type == "hip":
        raise UnsupportedRoofError(
            "nonrectangular primitive supports convex-quad gable/shed/flat only"
        )
    if roof_type in {"flat", "shed"}:
        semantics = {
            _key(i, (i + 1) % 4): (
                "eave"
                if roof_type == "flat" or i in (eave, (eave + 2) % 4)
                else "gable_end"
            )
            for i in range(4)
        }
        faces = (
            RoofFace(
                tuple(range(4)),
                (0,),
                tuple(range(4)) if roof_type == "flat" else (eave,),
            ),
        )
        return make_graph(
            outline,
            footprint.source_edges,
            outline,
            {i: BoundaryPoint(i, 0) for i in range(4)},
            ["corner"] * 4,
            faces,
            semantics,
            roof_type,
        )
    opposite = (eave + 2) % 4

    def distance(p, edge):
        a, b = outline[edge], outline[(edge + 1) % 4]
        vector = sub(b, a)
        return (vector[0] * (p[1] - a[1]) - vector[1] * (p[0] - a[0])) / math.hypot(
            *vector
        )

    seeds = list(outline)
    locations = {i: BoundaryPoint(i, 0) for i in range(4)}
    for side in ((eave + 1) % 4, (eave + 3) % 4):
        a, b = outline[side], outline[(side + 1) % 4]
        da = distance(a, eave) - distance(a, opposite)
        db = distance(b, eave) - distance(b, opposite)
        if abs(da - db) <= EPS:
            raise UnsupportedRoofError(
                "quad gable port lacks a unique equal-pitch bisector"
            )
        t = da / (da - db)
        if not EPS < t < 1 - EPS:
            raise UnsupportedRoofError("quad gable port degenerates at a corner")
        locations[len(seeds)] = BoundaryPoint(side, t)
        seeds.append(tuple(a[k] + t * (b[k] - a[k]) for k in (0, 1)))
    v = tuple((eave + i) % 4 for i in range(4))
    faces = (
        RoofFace((v[0], v[1], 4, 5), (0,), (eave,)),
        RoofFace((4, v[2], v[3], 5), (0,), (opposite,)),
    )
    semantics = {_key(v[0], v[1]): "eave", _key(v[2], v[3]): "eave", (4, 5): "ridge"}
    for a, b in ((v[1], 4), (4, v[2]), (v[3], 5), (5, v[0])):
        semantics[_key(a, b)] = "gable_end"
    return make_graph(
        outline,
        footprint.source_edges,
        seeds,
        locations,
        ["corner"] * 4 + ["ridge_end"] * 2,
        faces,
        semantics,
        roof_type,
    )
