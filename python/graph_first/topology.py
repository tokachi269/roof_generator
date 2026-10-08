# SPDX-License-Identifier: GPL-3.0-or-later
"""Primitive incidences and cell grafts decide topology without roof planes."""

import math
from dataclasses import dataclass, asdict
from collections import defaultdict
from .footprint import EPS, rectangle, on_segment, sub
from .graph import (
    BoundaryPoint,
    Face,
    RoofGraph,
    UnsupportedGraphError,
    make_graph,
    boundary_span,
)
from .geometry import harmonic_seeds, ridge_seeds
from .connections import plan


def _key(a, b):
    return tuple(sorted((a, b)))


def rectangle_graph(footprint, roof_type="gable", *, shed_edge=None):
    return _rectangle_graph(
        footprint.vertices, footprint.source_edges, roof_type, shed_edge=shed_edge
    )


def _rectangle_graph(outline, source_edges, roof_type, *, shed_edge=None, cell=0):
    if not rectangle(outline):
        raise UnsupportedGraphError("rectangle primitive requires a rectangle")
    if roof_type not in {"gable", "hip", "shed", "flat"}:
        raise UnsupportedGraphError("unsupported primitive type")
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
    if shed_edge is not None:
        if (
            roof_type != "shed"
            or not isinstance(shed_edge, int)
            or not 0 <= shed_edge < 4
        ):
            raise UnsupportedGraphError(
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
            Face(
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
        faces = tuple(Face((i, (i + 1) % 4, 4), (cell,), (i,)) for i in range(4))
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
                Face((v[0], v[1], 4, 5), (cell,), (base,)),
                Face((4, v[2], v[3], 5), (cell,), ((base + 2) % 4,)),
            )
            for a, b in ((v[0], v[1]), (v[2], v[3])):
                semantics[_key(a, b)] = "eave"
            for a, b in ((v[1], 4), (4, v[2]), (v[3], 5), (5, v[0])):
                semantics[_key(a, b)] = "gable_end"
        else:
            faces = (
                Face((v[0], v[1], 4, 5), (cell,), (base,)),
                Face((v[1], v[2], 4), (cell,), ((base + 1) % 4,)),
                Face((v[2], v[3], 5, 4), (cell,), ((base + 2) % 4,)),
                Face((v[3], v[0], 5), (cell,), ((base + 3) % 4,)),
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
class Connection:
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
    connections: tuple[Connection, ...]

    def inspect(self):
        return {
            "graph": self.graph.inspect(),
            "primitives": [g.inspect() for g in self.primitives],
            "connections": [asdict(c) for c in self.connections],
        }


def cell_primitives(decomposition, roof_type="gable"):
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
        )
        for cell in decomposition.cells
    )


def compose(decomposition, roof_type="gable"):
    fp = decomposition.footprint
    if len(decomposition.cells) == 1:
        g = rectangle_graph(fp, roof_type)
        return Composition(g, (g,), ())
    if roof_type != "gable":
        raise UnsupportedGraphError(
            "multi-cell composition currently supports gable only"
        )
    primitives = cell_primitives(decomposition)
    relations = plan(decomposition, primitives)
    if len(relations) == 1 and relations[0].kind == "terminal":
        return _terminal(decomposition, primitives, relations[0])
    raise UnsupportedGraphError(
        "middle attachment identified; cycle rewriting is not yet implemented"
    )


def _terminal(decomposition, primitives, relation):
    """The existing proved corner graft, driven by the published port relation."""
    fp = decomposition.footprint
    host, branch = relation.host, relation.branch
    hs, bs = relation.host_side, relation.branch_side
    hnear, bnear = relation.host_port, relation.branch_port
    hfar = next(
        i
        for i, v in enumerate(primitives[host].vertices)
        if v.role == "ridge_end" and i != hnear
    )
    bfar = next(
        i
        for i, v in enumerate(primitives[branch].vertices)
        if v.role == "ridge_end" and i != bnear
    )
    hc = decomposition.cells[host]
    cut_corner = next(iter(set(relation.shared).intersection(hc.sides[hs].vertices)))
    reflex = next(i for i in relation.shared if i != cut_corner)
    near_side = primitives[host].vertices[hnear].boundary.edge
    outer = next(i for i in hc.sides[near_side].vertices if i != cut_corner)
    seeds = list(fp.vertices)
    roles = ["corner"] * len(seeds)
    locations = {i: BoundaryPoint(i, 0) for i in range(len(seeds))}
    ports = {}
    for ci, local in ((host, hfar), (branch, bfar)):
        p = primitives[ci].vertices[local].seed
        candidates = [
            i
            for i, a in enumerate(fp.vertices)
            if on_segment(p, a, fp.vertices[(i + 1) % len(fp.vertices)])
        ]
        if len(candidates) != 1:
            raise UnsupportedGraphError(
                "surviving gable port lacks one physical boundary"
            )
        edge = candidates[0]
        a = fp.vertices[edge]
        v = sub(fp.vertices[(edge + 1) % len(fp.vertices)], a)
        t = sum(x * y for x, y in zip(sub(p, a), v)) / sum(x * x for x in v)
        ports[ci] = len(seeds)
        locations[len(seeds)] = BoundaryPoint(edge, t)
        seeds.append(p)
        roles.append("ridge_end")
    junction = len(seeds)
    seeds.append((0, 0))
    roles.append("junction")
    faces = []
    for ci, primitive in enumerate(primitives):
        cell = decomposition.cells[ci]
        near = hnear if ci == host else bnear
        mapping = {i: node for i, node in enumerate(cell.corners)}
        mapping.update({near: junction, (hfar if ci == host else bfar): ports[ci]})
        for face in primitive.faces:
            loop = []
            for a, b in zip(face.loop, face.loop[1:] + face.loop[:1]):
                if ci == host and a < 4 and mapping[a] == cut_corner:
                    pass  # The chord's exterior hit is redundant after grafting.
                elif ci == branch and a < 4 and mapping[a] == cut_corner:
                    loop.append(outer)
                else:
                    loop.append(mapping[a])
                if (
                    ci == host
                    and a < 4
                    and b < 4
                    and {mapping[a], mapping[b]} == set(cell.sides[hs].vertices)
                ):
                    loop.append(reflex)
            eaves = tuple(
                sorted(
                    {
                        span.edge
                        for side in face.eaves
                        for span in cell.sides[side].exterior
                    }
                )
            )
            faces.append(Face(tuple(loop), (ci,), eaves))
    widths = {
        host: math.dist(
            primitives[host].outline[primitives[host].vertices[hnear].boundary.edge],
            primitives[host].outline[
                (primitives[host].vertices[hnear].boundary.edge + 1) % 4
            ],
        ),
        branch: math.dist(
            primitives[branch].outline[bs], primitives[branch].outline[(bs + 1) % 4]
        ),
    }
    meanings = {
        _key(junction, ports[host]): "ridge",
        _key(junction, ports[branch]): "ridge",
        _key(junction, outer): "hip",
        _key(junction, reflex): "valley",
    }
    wider = None
    junctions = (junction,)
    if abs(widths[host] - widths[branch]) > EPS * 4:
        wider = max(widths, key=widths.get)
        narrow = branch if wider == host else host
        high, low = junction, junction + 1
        seeds.append((0, 0))
        roles.append("junction")
        junctions = (high, low)
        groups = {ports[wider]: high, outer: high, ports[narrow]: low, reflex: low}
        refined = []
        for face in faces:
            i = face.loop.index(junction)
            prev, nxt = face.loop[i - 1], face.loop[(i + 1) % len(face.loop)]
            replacement = (
                (groups[prev],)
                if groups[prev] == groups[nxt]
                else (groups[prev], groups[nxt])
            )
            refined.append(
                Face(
                    face.loop[:i] + replacement + face.loop[i + 1 :],
                    face.cells,
                    face.eaves,
                )
            )
        faces = refined
        meanings = {
            _key(groups[v], v): kind
            for v, kind in (
                (ports[host], "ridge"),
                (ports[branch], "ridge"),
                (outer, "hip"),
                (reflex, "valley"),
            )
        }
        meanings[high, low] = "hip"
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
    seeds = ridge_seeds(fp.vertices, seeds, faces, locations, meanings)
    graph = make_graph(
        fp.vertices, fp.source_edges, seeds, locations, roles, faces, meanings, "gable"
    )
    return Composition(
        graph,
        primitives,
        (
            Connection(
                host,
                branch,
                _key(*relation.shared),
                (hnear, bnear),
                junctions,
                wider,
            ),
        ),
    )
