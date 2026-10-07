# SPDX-License-Identifier: GPL-3.0-or-later
"""Planar source-mesh boundary extraction and placement of the final roof mesh."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import numpy as np

from .mesh_frame import (
    MeshSpec,
    PlaneFrame,
    project_planar_mesh_to_primal,
    lift_local_vertices_to_world,
)
from .core.roof_geometry import UnsupportedRoofError
from shapely.geometry import Polygon
from shapely.ops import unary_union
from .core.roof_building import RoofParameters, generate_roof


@dataclass(frozen=True)
class FootprintMeshResult:
    spec: MeshSpec
    roof: object
    frame: PlaneFrame


def generate_footprint_mesh(
    vertices,
    faces,
    parameters=RoofParameters(),
    *,
    mesh_name="roof",
    normal_hint=(0, 0, 1),
    part_parameters=None,
    mesh_origin=None,
):
    try:
        xy, faces, frame = project_planar_mesh_to_primal(vertices, faces)
    except ValueError as exc:
        raise UnsupportedRoofError(str(exc)) from exc
    n = np.asarray(frame.axis_n)
    hint = np.asarray(normal_hint, float)
    if hint.shape != (3,) or not np.isfinite(hint).all() or np.linalg.norm(hint) == 0:
        raise UnsupportedRoofError("normal_hint must be a finite nonzero 3D direction")
    if abs(float(np.dot(n, hint))) < 1e-6:
        raise UnsupportedRoofError(
            "footprint plane normal is perpendicular to the requested roof direction"
        )
    if np.dot(n, hint) < 0:
        frame = PlaneFrame(
            frame.origin, frame.axis_u, tuple(-np.asarray(frame.axis_v)), tuple(-n)
        )
        xy[:, 1] *= -1
    if not faces:
        raise UnsupportedRoofError(
            "source footprint must be a filled planar mesh, not an unordered point cloud"
        )
    incidence = defaultdict(list)
    polygons = []
    for face in faces:
        if (
            len(face) < 3
            or len(set(face)) != len(face)
            or any(i < 0 or i >= len(xy) for i in face)
        ):
            raise UnsupportedRoofError("invalid source footprint face indices")
        poly = Polygon(xy[list(face)])
        if not poly.is_valid or poly.area <= 0:
            raise UnsupportedRoofError(
                "source footprint has a self-crossing or zero-area face"
            )
        polygons.append(poly)
        for a, b in zip(face, face[1:] + face[:1]):
            incidence[tuple(sorted((a, b)))].append((a, b))
    adjacency = defaultdict(set)
    for (a, b), items in incidence.items():
        if len(items) > 2:
            raise UnsupportedRoofError("source footprint contains a nonmanifold edge")
        if len(items) == 1:
            adjacency[a].add(b)
            adjacency[b].add(a)
        elif items[0] != tuple(reversed(items[1])):
            raise UnsupportedRoofError("source footprint face normals are inconsistent")
    if not adjacency or any(len(n) != 2 for n in adjacency.values()):
        raise UnsupportedRoofError(
            "source footprint boundary must be one simple closed loop"
        )
    start = min(adjacency)
    loop = [start]
    previous = None
    current = start
    while True:
        candidates = sorted(
            adjacency[current] - ({previous} if previous is not None else set())
        )
        nxt = candidates[0]
        if nxt == start:
            break
        if nxt in loop:
            raise UnsupportedRoofError("source footprint boundary is pinched")
        loop.append(nxt)
        previous, current = current, nxt
    if len(loop) != len(adjacency):
        raise UnsupportedRoofError(
            "multiple footprint boundaries/holes are unsupported"
        )
    footprint = Polygon(xy[loop])
    union = unary_union(polygons)
    tolerance = max(footprint.length, 1) * 1e-8
    if (
        not footprint.is_valid
        or union.symmetric_difference(footprint).area > tolerance * footprint.length
        or sum(p.area for p in polygons) - union.area > tolerance * footprint.length
    ):
        raise UnsupportedRoofError(
            "source mesh does not form one nonoverlapping filled footprint"
        )
    roof = generate_roof(xy[loop], parameters, part_parameters=part_parameters)
    anchor = np.asarray(
        frame.origin if mesh_origin is None else mesh_origin, dtype=float
    )
    if anchor.shape != (3,) or not np.isfinite(anchor).all():
        raise UnsupportedRoofError("mesh origin must be a finite world-space 3D point")
    world = np.asarray(lift_local_vertices_to_world(roof.mesh.vertices, frame))
    spec = MeshSpec(
        name=mesh_name,
        vertices=tuple(map(tuple, world - anchor)),
        faces=roof.mesh.faces,
        location=tuple(anchor),
        color=(0.42, 0.17, 0.085, 1.0),
        face_int_attributes={
            "roof_part_i": tuple(parts[0] for parts in roof.mesh.face_parts)
        },
    )
    return FootprintMeshResult(spec, roof, frame)
