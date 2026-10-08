# SPDX-License-Identifier: GPL-3.0-or-later
"""Scalar metric plane projection and final mesh transport, without Blender."""

from dataclasses import dataclass, field
import math


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross3(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def unit(a):
    size = math.sqrt(dot(a, a))
    if not math.isfinite(size) or size <= 0:
        raise ValueError("footprint has no nondegenerate plane")
    return tuple(x / size for x in a)


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
    try:
        points = tuple(tuple(float(x) for x in p) for p in vertices)
    except (TypeError, ValueError) as exc:
        raise ValueError("footprint needs finite 3D vertices") from exc
    if len(points) < 3 or any(
        len(p) != 3 or not all(math.isfinite(x) for x in p) for p in points
    ):
        raise ValueError("footprint needs at least three finite 3D vertices")
    origin = points[0]
    offsets = tuple(tuple(p[k] - origin[k] for k in range(3)) for p in points)
    edge = max(offsets, key=lambda p: dot(p, p))
    normal = max((cross3(edge, p) for p in offsets), key=lambda p: dot(p, p))
    if math.sqrt(dot(normal, normal)) <= tolerance**2:
        raise ValueError("footprint has no nondegenerate plane")
    normal = unit(normal)
    if any(abs(dot(p, normal)) > tolerance for p in offsets):
        raise ValueError("footprint vertices are not planar within tolerance")
    u = unit(edge)
    v = cross3(normal, u)
    loops = tuple(tuple(f) for f in faces)
    if any(
        any(isinstance(i, bool) or not isinstance(i, int) for i in f) for f in loops
    ):
        raise ValueError("source face indices must be integers")
    return (
        tuple((dot(p, u), dot(p, v)) for p in offsets),
        loops,
        PlaneFrame(origin, u, v, normal),
    )


def lift_local_vertices_to_world(vertices, frame):
    axes = (frame.axis_u, frame.axis_v, frame.axis_n)
    return tuple(
        tuple(
            frame.origin[k] + sum(p[i] * axes[i][k] for i in range(3)) for k in range(3)
        )
        for p in vertices
    )
