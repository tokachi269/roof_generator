# SPDX-License-Identifier: GPL-3.0-or-later
"""Primitive incidences and cell grafts decide topology without roof planes."""

import math
from .footprint import rectangle
from .graph import BoundaryPoint, Face, UnsupportedGraphError, make_graph
from .geometry import harmonic_seeds


def _key(a, b):
    return tuple(sorted((a, b)))


def rectangle_graph(footprint, roof_type="gable", *, shed_edge=None):
    outline = footprint.vertices
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
                (0, 1, 2, 3), (0,), tuple(range(4)) if roof_type == "flat" else (base,)
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
        faces = tuple(Face((i, (i + 1) % 4, 4), (0,), (i,)) for i in range(4))
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
                Face((v[0], v[1], 4, 5), (0,), (base,)),
                Face((4, v[2], v[3], 5), (0,), ((base + 2) % 4,)),
            )
            for a, b in ((v[0], v[1]), (v[2], v[3])):
                semantics[_key(a, b)] = "eave"
            for a, b in ((v[1], 4), (4, v[2]), (v[3], 5), (5, v[0])):
                semantics[_key(a, b)] = "gable_end"
        else:
            faces = (
                Face((v[0], v[1], 4, 5), (0,), (base,)),
                Face((v[1], v[2], 4), (0,), ((base + 1) % 4,)),
                Face((v[2], v[3], 5, 4), (0,), ((base + 2) % 4,)),
                Face((v[3], v[0], 5), (0,), ((base + 3) % 4,)),
            )
            for i in range(4):
                semantics[_key(i, (i + 1) % 4)] = "eave"
            for a, b in ((v[1], 4), (v[2], 4), (v[3], 5), (v[0], 5)):
                semantics[_key(a, b)] = "hip"
        semantics[4, 5] = "ridge"
    seeds = harmonic_seeds(seeds, faces, locations)
    return make_graph(
        outline,
        footprint.source_edges,
        seeds,
        locations,
        roles,
        faces,
        semantics,
        roof_type,
    )
