# SPDX-License-Identifier: GPL-3.0-or-later
"""Complete adjacent roof solids, intersect their planes and remove hidden faces."""

from __future__ import annotations

from dataclasses import dataclass, replace
import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .roof_geometry import (
    EPS,
    GRID,
    clip,
    inward_plane,
    polygon_pieces,
    precise,
    UnsupportedRoofError,
)
from .roof_parts import RoofPart
from .roof_features import RoofFeature, region_features
from .roof_planes import RoofSolid, RoofPatch, RoofPlane, primitive, plane_patches


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
    regions: tuple[RoofRegion, ...]
    connections: tuple[Connection, ...]
    features: tuple[RoofFeature, ...] = ()


def connect(parts, footprint) -> RoofTopology:
    solids = tuple(primitive(part) for part in parts)
    planes = []
    exterior_planes = []
    for solid in solids:
        exterior = {source.part_edge for source in solid.part.source_edges}
        # A slope on a cut alone belongs to the isolated primitive only. It
        # must not turn a construction boundary into a valley at eave height.
        slopes = tuple(
            p
            for p in solid.planes
            if p.source_edge is None or p.source_edge in exterior
        )
        planes.append({plane.key: plane for plane in slopes})
        exterior_planes.append(
            {plane.key: plane for plane in slopes if plane.source_edge is not None}
        )
    # Propagate geometrically compatible exterior eave supports across the
    # adjacency graph. No shape/junction classes participate in this closure.
    changed = True
    while changed:
        changed = False
        for solid in solids:
            coords = np.asarray(solid.part.footprint.exterior.coords)[:-1]
            for neighbor in solid.part.neighbors:
                for key, plane in tuple(exterior_planes[neighbor.part_id].items()):
                    if key in exterior_planes[solid.part.id]:
                        continue
                    if min(plane.height(p) - plane.eave_height for p in coords) >= -EPS:
                        exterior_planes[solid.part.id][key] = plane
                        planes[solid.part.id][key] = plane
                        changed = True
    completed = []
    for solid in solids:
        part = solid.part
        coords = np.asarray(part.footprint.exterior.coords)[:-1]
        exterior = {source.part_edge for source in part.source_edges}
        domain = footprint
        for edge in sorted(exterior):
            domain = clip(
                domain, inward_plane(coords[edge], coords[(edge + 1) % len(coords)])
            )
        if not planes[part.id]:
            raise UnsupportedRoofError(
                f"part {part.id} has no exterior roof support after connecting cuts"
            )
        definitions = tuple(planes[part.id][key] for key in sorted(planes[part.id]))
        for plane in definitions:
            if np.linalg.norm(plane.coefficients[:2]) > GRID:
                domain = clip(domain, plane.coefficients, part.parameters.eave_height)
        completed.append(RoofSolid(part, definitions, domain))
    patches = tuple(p for solid in completed for p in plane_patches(solid))
    visible = []
    for i, patch in enumerate(patches):
        region = patch.polygon
        for j, other in enumerate(patches):
            if i == j or region.is_empty:
                continue
            overlap = region.intersection(other.polygon)
            if overlap.is_empty or overlap.area <= EPS**2:
                continue
            if patch.plane.key == other.plane.key:
                # Stable ownership of coincident roof surfaces.
                if j < i:
                    region = precise(region.difference(other.polygon))
                continue
            # Exposed upper envelope: discard the part of the overlap where
            # the other plane is higher. Boundary = plane-plane intersection.
            delta = tuple(
                b - a
                for a, b in zip(patch.plane.coefficients, other.plane.coefficients)
            )
            concealed = clip(overlap, delta)
            if not concealed.is_empty:
                region = precise(region.difference(concealed))
        for poly in polygon_pieces(region):
            visible.append(RoofPatch(poly, patch.plane, patch.part_id))
    by_plane = {}
    for patch in visible:
        by_plane.setdefault(patch.plane.key, []).append(patch)
    regions = []
    for key, group in sorted(by_plane.items()):
        # Final overlay uses a common numerical tolerance grid. GEOS
        # removes sub-tolerance slits/spikes here, before topology indexing;
        # leaving them until welding would create pinched/repeated loops.
        union = shapely.orient_polygons(
            shapely.set_precision(unary_union([p.polygon for p in group]), EPS)
        )
        for poly in polygon_pieces(union):
            contributors = tuple(
                sorted(
                    {
                        p.part_id
                        for p in group
                        if p.polygon.intersection(poly).area > EPS**2
                    }
                )
            )
            regions.append(RoofRegion(poly, group[0].plane, contributors))
    cover = unary_union([region.polygon for region in regions])
    if footprint.symmetric_difference(cover).area > EPS:
        raise UnsupportedRoofError("connected roof does not cover the entire footprint")
    # Check continuity before indexing/triangulation. Discontinuous height
    # offsets are unsupported, never left for the Blender layer to repair.
    connections = []
    for i, a in enumerate(regions):
        for b in regions[i + 1 :]:
            common = precise(a.polygon.boundary).intersection(
                precise(b.polygon.boundary)
            )
            if common.length > EPS:
                for point in shapely.get_coordinates(common):
                    if abs(
                        a.plane.height(point) - b.plane.height(point)
                    ) > EPS * 8 * max(
                        1.0,
                        np.linalg.norm(a.plane.coefficients[:2]),
                        np.linalg.norm(b.plane.coefficients[:2]),
                    ):
                        raise UnsupportedRoofError(
                            "incompatible roof height difference at connector; vertical steps require an explicit wall/flashing design"
                        )
    for part in parts:
        for neighbor in part.neighbors:
            if neighbor.part_id <= part.id:
                continue
            pairs = tuple(
                (a.coefficients, b.coefficients)
                for a in completed[part.id].planes
                for b in completed[neighbor.part_id].planes
                if a.key != b.key
            )
            connections.append(
                Connection((part.id, neighbor.part_id), neighbor.shared_boundary, pairs)
            )
    connected_parts = tuple(
        replace(s.part, plane_definitions=tuple(p.coefficients for p in s.planes))
        for s in completed
    )
    return RoofTopology(
        footprint,
        connected_parts,
        tuple(regions),
        tuple(connections),
        region_features(regions, connected_parts),
    )
