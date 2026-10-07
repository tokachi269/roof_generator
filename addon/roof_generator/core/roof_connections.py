# SPDX-License-Identifier: GPL-3.0-or-later
"""Complete adjacent roof solids, intersect their planes and remove hidden faces."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from shapely.geometry import Polygon
from .roof_features import RoofFeature
from .roof_parts import RoofPart
from .roof_planes import RoofPlane
from .roof_graph import RoofGraph, build_graph


@dataclass(frozen=True)
class RoofRegion:
    polygon: Polygon
    plane: RoofPlane
    part_ids: tuple[int, ...]


@dataclass(frozen=True)
class Connection:
    parts: tuple[int, int]
    shared_boundary: tuple
    plane_pairs: tuple[
        tuple[tuple[float, float, float], tuple[float, float, float]], ...
    ]


@dataclass(frozen=True)
class RoofTopology:
    footprint: Polygon
    parts: tuple[RoofPart, ...]
    graph: RoofGraph
    connections: tuple[Connection, ...]
    features: tuple[RoofFeature, ...] = ()

    @cached_property
    def regions(self):
        # Derived planar geometry for analysis/export, never topology discovery.
        return tuple(
            RoofRegion(
                Polygon(
                    [self.graph.vertices[v] for v in face.outer],
                    [[self.graph.vertices[v] for v in hole] for hole in face.holes],
                ),
                face.plane,
                face.part_ids,
            )
            for face in self.graph.faces
        )


def connect(parts, footprint) -> RoofTopology:
    from .roof_features import classify_crease

    graph = build_graph(parts, footprint)
    xyz = graph.embed()
    features = []
    for a, b, i, j in graph.edges:
        if j < 0:
            continue
        first, second = graph.faces[i], graph.faces[j]
        kind = classify_crease(
            first.plane,
            second.plane,
            (graph.vertices[a], graph.vertices[b]),
            graph.parts,
        )
        if kind is not None:
            features.append(
                RoofFeature(
                    kind,
                    (xyz[a], xyz[b]),
                    (i, j),
                    tuple(sorted(set(first.part_ids + second.part_ids))),
                )
            )
    connections = tuple(
        Connection(
            (part.id, neighbor.part_id),
            neighbor.shared_boundary,
            tuple(
                (a, b)
                for a in graph.parts[part.id].plane_definitions
                for b in graph.parts[neighbor.part_id].plane_definitions
                if a != b
            ),
        )
        for part in graph.parts
        for neighbor in part.neighbors
        if neighbor.part_id > part.id
    )
    return RoofTopology(
        footprint,
        graph.parts,
        graph,
        connections,
        tuple(sorted(features, key=lambda f: (f.kind, f.segment))),
    )
