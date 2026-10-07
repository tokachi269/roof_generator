# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent metric plane projection and final mesh transport types."""

from dataclasses import dataclass, field
import numpy as np


@dataclass(frozen=True)
class PlaneFrame:
    origin: tuple
    axis_u: tuple
    axis_v: tuple
    axis_n: tuple


@dataclass(frozen=True)
class MeshSpec:
    name: str
    vertices: tuple
    faces: tuple
    location: tuple
    color: tuple
    face_int_attributes: dict = field(default_factory=dict)


def project_planar_mesh(vertices, faces, tolerance=1e-5):
    points = np.asarray(vertices, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 3:
        raise ValueError("footprint needs at least three finite 3D vertices")
    if not np.isfinite(points).all():
        raise ValueError("footprint vertices must be finite")
    origin = points[0]
    offsets = points - origin
    _, values, basis = np.linalg.svd(offsets, full_matrices=False)
    if values[1] <= tolerance:
        raise ValueError("footprint has no nondegenerate plane")
    normal = basis[-1]
    if np.max(np.abs(offsets @ normal)) > tolerance:
        raise ValueError("footprint vertices are not planar within tolerance")
    # A source edge defines coordinates; SVD determines only the plane normal.
    edge = next((v for v in offsets[1:] if np.linalg.norm(v) > tolerance), None)
    if edge is None:
        raise ValueError("footprint has no usable edge")
    u = edge - np.dot(edge, normal) * normal
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    frame = PlaneFrame(tuple(origin), tuple(u), tuple(v), tuple(normal))
    return (
        np.column_stack((offsets @ u, offsets @ v)),
        tuple(tuple(int(i) for i in f) for f in faces),
        frame,
    )


def lift_local_vertices_to_world(vertices, frame):
    coordinates = np.asarray(vertices, dtype=float)
    axes = np.array([frame.axis_u, frame.axis_v, frame.axis_n])
    return tuple(map(tuple, coordinates @ axes + frame.origin))
