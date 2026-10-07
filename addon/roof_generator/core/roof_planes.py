# SPDX-License-Identifier: GPL-3.0-or-later
"""Convex-part roof solids and their exact affine plane patches."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
import numpy as np
from shapely.geometry import Polygon

from .roof_geometry import (
    EPS,
    GRID,
    UnsupportedRoofError,
    clip,
    inward_plane,
    plane_value,
    polygon_pieces,
    precise,
)
from .roof_parts import RoofPart


@dataclass(frozen=True)
class RoofPlane:
    coefficients: tuple[float, float, float]  # z = ax + by + c
    source_part: int
    source_edge: int | None
    eave_height: float

    @property
    def key(self):
        return tuple(round(x, 10) for x in self.coefficients)

    def height(self, point):
        return plane_value(self.coefficients, point)


@dataclass(frozen=True)
class RoofPatch:
    polygon: Polygon
    plane: RoofPlane
    part_id: int


@dataclass(frozen=True)
class RoofSolid:
    part: RoofPart
    planes: tuple[RoofPlane, ...]
    domain: Polygon


def primitive(part: RoofPart) -> RoofSolid:
    params = part.parameters
    if params.roof_type not in {"flat", "gable", "hip", "shed"}:
        raise UnsupportedRoofError("unsupported roof type")
    if not math.isfinite(params.eave_height) or not math.isfinite(params.pitch):
        raise UnsupportedRoofError("eave height and pitch must be finite")
    if params.roof_type != "flat" and params.pitch <= 0:
        raise UnsupportedRoofError("pitched roofs require a positive rise/run pitch")
    coords = np.asarray(part.footprint.exterior.coords)[:-1]
    if not part.geometry.convex or len(coords) not in {3, 4}:
        raise UnsupportedRoofError(
            "a roof primitive must have a convex triangle/quad footprint"
        )
    definitions = []
    if params.planes:
        for plane in params.planes:
            if len(plane) != 3 or not np.isfinite(plane).all():
                raise UnsupportedRoofError(
                    "explicit roof planes must be finite (a,b,c) tuples"
                )
            definitions.append(
                RoofPlane(tuple(plane), part.id, None, params.eave_height)
            )
    elif params.roof_type == "flat":
        definitions = [
            RoofPlane((0.0, 0.0, params.eave_height), part.id, None, params.eave_height)
        ]
    else:
        exterior = {s.part_edge for s in part.source_edges}
        if params.roof_type == "hip":
            edges = range(len(coords))
        elif params.roof_type == "gable":
            if len(coords) != 4:
                raise UnsupportedRoofError("gable requires a convex quadrilateral")
            lengths = np.linalg.norm(np.roll(coords, -1, axis=0) - coords, axis=1)
            pair = params.eave_pair
            if pair is None:
                pair = min(
                    [(0, 2), (1, 3)],
                    key=lambda x: (
                        sum(i not in exterior for i in x),
                        -round(sum(lengths[list(x)]), 10),
                        x,
                    ),
                )
            if tuple(sorted(pair)) not in {(0, 2), (1, 3)}:
                raise UnsupportedRoofError(
                    "gable eaves must be opposite edges of the normalized quad"
                )
            edges = pair
        else:
            if len(coords) != 4:
                raise UnsupportedRoofError("shed requires a convex quadrilateral")
            lengths = np.linalg.norm(np.roll(coords, -1, axis=0) - coords, axis=1)
            edge = params.shed_edge
            if edge is None:
                candidates = sorted(exterior) or list(range(len(coords)))
                edge = min(candidates, key=lambda i: (-round(float(lengths[i]), 10), i))
            if not isinstance(edge, int) or not 0 <= edge < len(coords):
                raise UnsupportedRoofError(
                    "shed_edge must index a normalized part edge"
                )
            edges = [edge]
        for edge in edges:
            a, b, c = inward_plane(coords[edge], coords[(edge + 1) % len(coords)])
            definitions.append(
                RoofPlane(
                    (
                        params.pitch * a,
                        params.pitch * b,
                        params.eave_height + params.pitch * c,
                    ),
                    part.id,
                    edge,
                    params.eave_height,
                )
            )
    part = replace(
        part,
        plane_definitions=tuple(p.coefficients for p in definitions),
        provenance=part.provenance + ("supporting-edge affine roof planes",),
    )
    if len(definitions) == 2:
        delta = (
            np.asarray(definitions[0].coefficients[:2])
            - definitions[1].coefficients[:2]
        )
        if np.linalg.norm(delta) <= EPS:
            raise UnsupportedRoofError("gable eave planes do not define a ridge")
        direction = np.array([-delta[1], delta[0]]) / np.linalg.norm(delta)
        part = replace(part, ridge_orientation=tuple(direction))
    solid = RoofSolid(part, tuple(definitions), part.footprint)
    patches = plane_patches(solid)
    if not patches or (
        params.roof_type == "gable" and not params.planes and len(patches) != 2
    ):
        raise UnsupportedRoofError(
            "the requested primitive does not have valid exposed roof faces"
        )
    return solid


def plane_patches(solid: RoofSolid):
    patches = []
    # Each patch is obtained from min_j plane_j, not a triangulated height fan.
    for i, plane in enumerate(solid.planes):
        region = solid.domain
        for j, other in enumerate(solid.planes):
            if i == j:
                continue
            if plane.key == other.key:
                if j < i:
                    region = Polygon()
                    break
                continue
            delta = tuple(b - a for a, b in zip(plane.coefficients, other.coefficients))
            region = clip(region, delta)
            if region.is_empty:
                break
        for poly in polygon_pieces(region):
            patches.append(RoofPatch(precise(poly), plane, solid.part.id))
    return tuple(patches)
