# SPDX-License-Identifier: GPL-3.0-or-later
"""Test-only adapter into the unchanged secondary semantic snapshot reader.

Shapely exists only in this comparison adapter. It reads the new solved output;
it never generates cells, face incidence, features or topology for the new path.
"""

from types import SimpleNamespace as Record
import numpy as np
from shapely.geometry import Polygon
from python.roof_harness import snapshot


def rectangle_snapshot(footprint, mesh):
    graph = mesh.graph
    vertices = np.asarray(mesh.vertices)
    planes = []
    regions = []
    for face in graph.faces:
        points = vertices[list(face.loop)]
        plane = tuple(
            np.linalg.lstsq(
                np.column_stack((points[:, :2], np.ones(len(points)))),
                points[:, 2],
                rcond=None,
            )[0]
        )
        planes.append(plane)
        regions.append(
            Record(
                polygon=Polygon(points[:, :2]),
                plane=Record(coefficients=plane),
                part_ids=face.cells,
            )
        )
    sources = tuple(
        Record(
            footprint_edge=i,
            segment=(p, graph.outline[(i + 1) % len(graph.outline)]),
            original_edges=graph.source_edges[i],
        )
        for i, p in enumerate(graph.outline)
    )
    polygon = Polygon(graph.outline)
    part = Record(
        id=0,
        footprint=polygon,
        source_edges=sources,
        neighbors=(),
        plane_definitions=tuple(planes),
    )
    frame = Record(
        u=footprint.frame.direction,
        origin=footprint.frame.origin,
        scale=footprint.frame.scale,
    )
    worldmesh = Record(
        vertices=tuple(footprint.frame.world_xyz(p) for p in mesh.vertices),
        faces=mesh.faces,
        face_parts=mesh.face_parts,
        edge_features=mesh.edge_features,
    )
    result = Record(
        footprint=Record(frame=frame, polygon=polygon),
        topology=Record(parts=(part,), regions=tuple(regions)),
        mesh=worldmesh,
    )
    return snapshot(result)
