# SPDX-License-Identifier: GPL-3.0-or-later
"""Validated solved coordinates consuming one authoritative RoofGraph."""

from dataclasses import dataclass
from collections import defaultdict
import math
from .graph import RoofGraph, UnsupportedRoofError
from .footprint import EPS, sub, rectangle, area, inside, on_segment, cross, _intersects


from .initialization import _valid_drawing


@dataclass(frozen=True)
class RoofMesh:
    graph: RoofGraph
    vertices: tuple[tuple[float, float, float], ...]

    def __post_init__(self):
        if len(self.vertices) != len(self.graph.vertices) or any(
            len(p) != 3 or not all(math.isfinite(v) for v in p) for p in self.vertices
        ):
            raise UnsupportedRoofError("mesh coordinates violate graph vertex contract")
        for i, p in enumerate(self.vertices):
            if (
                self.graph.vertices[i].boundary is not None
                and math.dist(p[:2], self.graph.vertices[i].seed) > EPS * 20
            ):
                raise UnsupportedRoofError("mesh moves fixed footprint boundary")
            if any(math.dist(p, q) <= EPS for q in self.vertices[:i]):
                raise UnsupportedRoofError("mesh has coincident graph vertices")
        if not _valid_drawing(
            self.graph.outline,
            tuple(p[:2] for p in self.vertices),
            self.graph.faces,
            {i for i, v in enumerate(self.graph.vertices) if v.boundary is not None},
            {e.vertices: e.kind for e in self.graph.edges},
        ):
            raise UnsupportedRoofError("mesh has an invalid footprint projection")
        for face in self.graph.faces:
            points = tuple(self.vertices[i] for i in face.loop)
            if area(tuple(p[:2] for p in points)) <= EPS**2:
                raise UnsupportedRoofError("mesh face has nonpositive projection")
            # Oriented polygon normal, not the first fan triangle: a concave
            # face can start at a reflex vertex while its cycle remains CCW.
            offsets = tuple(
                tuple(p[k] - points[0][k] for k in range(3)) for p in points
            )
            candidate = tuple(
                sum(
                    a[(k + 1) % 3] * b[(k + 2) % 3] - a[(k + 2) % 3] * b[(k + 1) % 3]
                    for a, b in zip(offsets, offsets[1:] + offsets[:1])
                )
                for k in range(3)
            )
            size = math.sqrt(sum(v * v for v in candidate))
            normal = tuple(v / size for v in candidate) if size > EPS**2 else None
            if (
                normal is None
                or normal[2] <= 0
                or any(
                    abs(sum((p[k] - points[0][k]) * normal[k] for k in range(3)))
                    > EPS * 20
                    for p in points
                )
            ):
                raise UnsupportedRoofError(
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
