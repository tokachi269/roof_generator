# SPDX-License-Identifier: GPL-3.0-or-later
"""Tessellate already-decided planar topology and share all edge vertices."""

from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
import numpy as np

from .roof_geometry import (
    EPS,
    UnsupportedRoofError,
    clean_ring,
    polygon_pieces,
)
import shapely
from .roof_features import classify_crease


@dataclass(frozen=True)
class RoofMesh:
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, ...], ...]
    face_parts: tuple[tuple[int, ...], ...]
    # Features contain only geometric creases/perimeter, never tessellation cuts.
    edge_features: dict[tuple[int, int], str]


WELD = EPS * 4


def tessellate(topology) -> RoofMesh:
    graph = topology.graph
    vertices = graph.embed()
    faces, regions = [], []
    for region in graph.faces:
        if region.holes:
            from shapely.geometry import Polygon

            polygon = Polygon(
                [graph.vertices[i] for i in region.outer],
                [[graph.vertices[i] for i in hole] for hole in region.holes],
            )
            polygons = polygon_pieces(shapely.constrained_delaunay_triangles(polygon))
            loops = []
            for triangle in polygons:
                loop = []
                for p in clean_ring(triangle.exterior.coords):
                    hits = [
                        i
                        for i, q in enumerate(graph.vertices)
                        if np.linalg.norm(np.asarray(p) - q) <= WELD
                    ]
                    if len(hits) != 1:
                        raise UnsupportedRoofError(
                            "tessellation vertex is not a unique roof graph node"
                        )
                    loop.append(hits[0])
                loops.append(tuple(loop))
        else:
            loops = (region.outer,)
        for loop in loops:
            if len(loop) < 3 or len(set(loop)) != len(loop):
                raise UnsupportedRoofError("invalid roof graph face loop")
            start = min(range(len(loop)), key=lambda i: loop[i])
            faces.append(loop[start:] + loop[:start])
            regions.append(region)
    order = sorted(range(len(faces)), key=lambda i: faces[i])
    faces = tuple(faces[i] for i in order)
    regions = [regions[i] for i in order]
    incidence = defaultdict(list)
    for i, face in enumerate(faces):
        for a, b in zip(face, face[1:] + face[:1]):
            incidence[tuple(sorted((a, b)))].append((i, a, b))
    features = {}
    for edge, adjacent in sorted(incidence.items()):
        if len(adjacent) == 1:
            h0, h1 = vertices[edge[0]][2], vertices[edge[1]][2]
            features[edge] = "eave" if abs(h0 - h1) <= EPS else "gable_end"
        elif len(adjacent) == 2:
            (i, a, b), (j, _, _) = adjacent
            kind = classify_crease(
                regions[i].plane,
                regions[j].plane,
                (graph.vertices[a], graph.vertices[b]),
                topology.parts,
            )
            if kind is not None:
                features[edge] = kind
        else:
            raise UnsupportedRoofError("more than two faces meet on a roof edge")
    return RoofMesh(
        vertices, faces, tuple(region.part_ids for region in regions), features
    )
