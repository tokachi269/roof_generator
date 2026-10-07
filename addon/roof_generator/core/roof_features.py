# SPDX-License-Identifier: GPL-3.0-or-later
"""Roof crease semantics on planar regions, before any mesh tessellation."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import shapely
from shapely.geometry import LineString, Point

from .roof_geometry import EPS, UnsupportedRoofError, precise


@dataclass(frozen=True)
class RoofFeature:
    kind: str
    segment: tuple[tuple[float, float, float], tuple[float, float, float]]
    regions: tuple[int, int]
    part_ids: tuple[int, ...]


def classify_crease(plane_a, plane_b, oriented_segment, parts):
    """The segment follows region A's boundary with its interior on the left."""
    a, b = np.asarray(oriented_segment, dtype=float)
    direction = b - a
    inward = np.array([-direction[1], direction[0]]) / np.linalg.norm(direction)
    ga, gb = np.asarray(plane_a.coefficients[:2]), np.asarray(plane_b.coefficients[:2])
    curvature = float(np.dot(ga - gb, inward))
    if abs(curvature) <= EPS:
        return None  # coplanar export subdivisions are not roof topology
    if curvature > 0:
        return "valley"
    opposite = (
        plane_a.source_part == plane_b.source_part
        and len(parts[plane_a.source_part].footprint.exterior.coords) == 5
        and plane_a.source_edge is not None
        and plane_b.source_edge is not None
        and abs(plane_a.source_edge - plane_b.source_edge) == 2
    )
    opposing = abs(ga[0] * gb[1] - ga[1] * gb[0]) <= EPS and np.dot(ga, gb) < 0
    horizontal = abs(plane_a.height(a) - plane_a.height(b)) <= EPS
    return "ridge" if opposite or opposing or horizontal else "hip"


def region_features(regions, parts):
    result = []
    for i, first in enumerate(regions):
        for j in range(i + 1, len(regions)):
            second = regions[j]
            shared = precise(first.polygon.boundary).intersection(
                precise(second.polygon.boundary)
            )
            for line in shapely.get_parts(shared):
                if line.geom_type != "LineString" or line.length <= EPS:
                    continue
                coords = list(line.coords)
                for a, b in zip(coords, coords[1:]):
                    if np.linalg.norm(np.asarray(b) - a) <= EPS:
                        continue
                    midpoint = Point((np.asarray(a) + b) / 2)
                    oriented = None
                    # Exterior CCW / interior CW rings both place the region
                    # on the left. Recover only the direction of the existing
                    # boundary; never infer a new crease from a face center.
                    for ring in [first.polygon.exterior, *first.polygon.interiors]:
                        points = list(ring.coords)
                        for p, q in zip(points, points[1:]):
                            if LineString([p, q]).distance(midpoint) <= EPS:
                                sign = np.dot(np.asarray(b) - a, np.asarray(q) - p)
                                oriented = (a, b) if sign >= 0 else (b, a)
                                break
                        if oriented is not None:
                            break
                    if oriented is None:
                        raise UnsupportedRoofError(
                            "roof crease is not on its incident region boundary"
                        )
                    kind = classify_crease(first.plane, second.plane, oriented, parts)
                    if kind is not None:
                        segment = tuple(
                            (float(p[0]), float(p[1]), first.plane.height(p))
                            for p in oriented
                        )
                        result.append(
                            RoofFeature(
                                kind,
                                segment,
                                (i, j),
                                tuple(sorted(set(first.part_ids + second.part_ids))),
                            )
                        )
    return tuple(sorted(result, key=lambda feature: (feature.kind, feature.segment)))
