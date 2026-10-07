# SPDX-License-Identifier: GPL-3.0-or-later
"""Roof crease semantics on planar regions, before any mesh tessellation."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .roof_geometry import EPS


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
