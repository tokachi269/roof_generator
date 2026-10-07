# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate a connected, validated roof mesh from a planar footprint."""

from __future__ import annotations

from dataclasses import dataclass, replace
import numpy as np

from .roof_geometry import Footprint, EPS, normalize_footprint, UnsupportedRoofError
from .roof_parts import RoofParameters, Decomposition, decompose
from .roof_connections import RoofTopology, connect
from .roof_mesh import RoofMesh, tessellate
from .roof_validation import MeshValidation, validate_mesh
from shapely.errors import GEOSException


@dataclass(frozen=True)
class RoofResult:
    mesh: RoofMesh
    normalized_mesh: RoofMesh
    footprint: Footprint
    decomposition: Decomposition
    topology: RoofTopology
    validation: MeshValidation


def generate_roof(
    vertices, parameters=RoofParameters(), *, part_parameters=None, max_states=12000
):
    try:
        footprint = normalize_footprint(vertices)
        frame = footprint.frame

        def local(params):
            definitions = []
            u = np.asarray(frame.u)
            v = np.array([-u[1], u[0]])
            for definition in params.planes:
                plane = np.asarray(definition, dtype=float)
                if plane.shape != (3,) or not np.isfinite(plane).all():
                    raise UnsupportedRoofError(
                        "explicit roof planes must be finite (a,b,c) tuples"
                    )
                a, b, c = plane
                definitions.append(
                    (
                        float(np.dot([a, b], u)),
                        float(np.dot([a, b], v)),
                        float((np.dot([a, b], frame.origin) + c) / frame.scale),
                    )
                )
            return replace(
                params,
                eave_height=params.eave_height / frame.scale,
                planes=tuple(definitions),
            )

        decomposition = decompose(footprint, local(parameters), max_states=max_states)
        overrides = part_parameters or {}
        if set(overrides) - {part.id for part in decomposition.parts}:
            raise UnsupportedRoofError("part_parameters refers to a nonexistent part")
        parts = tuple(
            (
                replace(part, parameters=local(overrides[part.id]))
                if part.id in overrides
                else part
            )
            for part in decomposition.parts
        )
        decomposition = replace(decomposition, parts=parts)
        topology = connect(parts, footprint.polygon)
        mesh = tessellate(topology)
        # Validation is mandatory before returning a mesh. No optimizer, preview
        # fallback or Blender repair is allowed to mask a generator failure.
        validation = validate_mesh(mesh, footprint.polygon, tolerance=EPS * 20)
        world = RoofMesh(
            tuple(map(tuple, frame.lift(mesh.vertices))),
            mesh.faces,
            mesh.face_parts,
            mesh.edge_features,
        )
        return RoofResult(world, mesh, footprint, decomposition, topology, validation)
    except GEOSException as exc:
        raise UnsupportedRoofError(
            f"polygon operations cannot resolve this footprint at numerical tolerance: {exc}"
        ) from exc
