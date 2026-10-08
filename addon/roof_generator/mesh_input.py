# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate a filled planar source mesh and transport canonical solved output."""

from collections import defaultdict
from dataclasses import dataclass, replace
import math
from types import SimpleNamespace
from .mesh_frame import (
    MeshSpec,
    PlaneFrame,
    project_planar_mesh,
    lift_local_vertices_to_world,
    dot,
    unit,
)
from .core.errors import UnsupportedRoofError
from .core.footprint import analyze, area, EPS
from .core.initialization import _valid_drawing
from .core.graph import _connected
from .core.generation import GenerationSettings, generate_roof


@dataclass(frozen=True)
class FootprintMeshResult:
    spec: MeshSpec
    roof: object
    frame: PlaneFrame


def source_outline(xy, faces):
    if not faces:
        raise UnsupportedRoofError("source footprint must be a filled planar mesh")
    if any(
        len(f) < 3 or len(set(f)) != len(f) or any(i < 0 or i >= len(xy) for i in f)
        for f in faces
    ):
        raise UnsupportedRoofError("invalid source footprint face indices")
    if {v for f in faces for v in f} != set(range(len(xy))):
        raise UnsupportedRoofError("source mesh has unused vertices")
    signed = tuple(area(tuple(xy[v] for v in f)) for f in faces)
    if any(abs(a) <= EPS**2 for a in signed) or any(a * signed[0] <= 0 for a in signed):
        raise UnsupportedRoofError(
            "source faces have zero area or inconsistent normals"
        )
    if signed[0] < 0:
        faces = tuple(tuple(reversed(f)) for f in faces)
    for f in faces:
        analyze(tuple(xy[v] for v in f))
    incidence = defaultdict(list)
    for fi, f in enumerate(faces):
        for a, b in zip(f, f[1:] + f[:1]):
            incidence[tuple(sorted((a, b)))].append((fi, a, b))
    boundary = {}
    neighbors = defaultdict(set)
    for items in incidence.values():
        if len(items) == 1:
            _, a, b = items[0]
            if a in boundary:
                raise UnsupportedRoofError("source boundary is touching or branched")
            boundary[a] = b
        elif len(items) == 2:
            (i, a, b), (j, c, d) = items
            if (a, b) != (d, c):
                raise UnsupportedRoofError("source face normals are inconsistent")
            neighbors[i].add(j)
            neighbors[j].add(i)
        else:
            raise UnsupportedRoofError("source footprint has nonmanifold edges")
    if not boundary or set(boundary) != set(boundary.values()):
        raise UnsupportedRoofError("source boundary is not a closed loop")
    start = min(boundary)
    loop = []
    v = start
    while v not in loop:
        loop.append(v)
        v = boundary[v]
    if v != start or len(loop) != len(boundary):
        raise UnsupportedRoofError("multiple boundaries or holes are unsupported")
    if len(faces) > 1 and not _connected(neighbors):
        raise UnsupportedRoofError("source faces are disconnected")
    if len(xy) - len(incidence) + len(faces) != 1:
        raise UnsupportedRoofError("source mesh is not a topological disk")
    outline = tuple(xy[v] for v in loop)
    # Independent source filling validation: indexed cycles and noncrossing
    # projection. No polygon Boolean, triangulation or output topology repair.
    if not _valid_drawing(
        outline,
        xy,
        tuple(SimpleNamespace(loop=f) for f in faces),
        set(loop),
        {edge: "source" for edge in incidence},
    ):
        raise UnsupportedRoofError("source mesh overlaps, crosses or has T-junctions")
    if (
        abs(sum(abs(a) for a in signed) - area(outline))
        > max(1, abs(area(outline))) * 1e-8
    ):
        raise UnsupportedRoofError("source faces do not cover the footprint")
    return outline


def generate_footprint_mesh(
    vertices,
    faces,
    settings=GenerationSettings(),
    *,
    mesh_name="roof",
    normal_hint=(0, 0, 1),
    reference_hint=None,
    mesh_origin=None
):
    try:
        xy, faces, frame = project_planar_mesh(vertices, faces)
        hint = unit(tuple(float(x) for x in normal_hint))
    except (TypeError, ValueError) as exc:
        raise UnsupportedRoofError(str(exc)) from exc
    if len(hint) != 3 or abs(dot(frame.axis_n, hint)) < 1e-6:
        raise UnsupportedRoofError(
            "footprint normal is perpendicular to roof direction"
        )
    if dot(frame.axis_n, hint) < 0:
        frame = PlaneFrame(
            frame.origin,
            frame.axis_u,
            tuple(-x for x in frame.axis_v),
            tuple(-x for x in frame.axis_n),
        )
        xy = tuple((x, -y) for x, y in xy)
    if reference_hint is not None:
        try:
            ref = unit(tuple(float(x) for x in reference_hint))
            if len(ref) != 3:
                raise ValueError("reference hint must be 3D")
            settings = replace(
                settings,
                reference_direction=(dot(ref, frame.axis_u), dot(ref, frame.axis_v)),
            )
        except (TypeError, ValueError) as exc:
            raise UnsupportedRoofError(str(exc)) from exc
    outline = source_outline(xy, faces)
    roof = generate_roof(outline, settings)
    anchor = tuple(frame.origin if mesh_origin is None else mesh_origin)
    if len(anchor) != 3 or not all(math.isfinite(x) for x in anchor):
        raise UnsupportedRoofError("mesh origin must be a finite world 3D point")
    metric = tuple(
        roof.generation.footprint.frame.world_xyz(p) for p in roof.mesh.vertices
    )
    world = lift_local_vertices_to_world(metric, frame)
    spec = MeshSpec(
        mesh_name,
        tuple(tuple(p[k] - anchor[k] for k in range(3)) for p in world),
        roof.mesh.faces,
        anchor,
        (0.42, 0.17, 0.085, 1),
        {"roof_cell_i": tuple(f.cells[0] for f in roof.mesh.graph.faces)},
    )
    return FootprintMeshResult(spec, roof, frame)
