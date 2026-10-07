# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "addon"))
from roof_generator.core.roof_geometry import (
    normalize_footprint,
    UnsupportedRoofError,
    polygon_ring,
)
from roof_generator.core.roof_parts import decompose, RoofParameters
from roof_generator.core.roof_partition import candidate_cuts
from shapely.geometry import Polygon
from shapely.ops import unary_union
import numpy as np


class PartitionSearchTests(unittest.TestCase):
    def test_convex_leaf_keeps_one_part_and_minimum_rectangle_aspect(self):
        footprint = normalize_footprint([(0, 0), (17, 0), (17, 9), (0, 9)])
        result = decompose(footprint)
        self.assertEqual(len(result.parts), 1)
        self.assertAlmostEqual(result.cost[1][0], 17 / 9, places=7)
        self.assertEqual(result.cuts, ())

    def test_pitch_and_eave_changes_reuse_partition_without_stale_parameters(self):
        footprint = normalize_footprint(
            [(0, 0), (13, 0), (13, 4), (5, 4), (5, 11), (0, 11)]
        )
        first = decompose(footprint, RoofParameters(pitch=0.4))
        changed = RoofParameters(pitch=0.7, eave_height=0.12)
        with patch(
            "roof_generator.core.roof_partition.candidate_cuts", wraps=candidate_cuts
        ) as observed:
            second = decompose(footprint, changed)
        observed.assert_not_called()
        self.assertEqual(first.cuts, second.cuts)
        self.assertEqual(first.cost, second.cost)
        self.assertTrue(all(part.parameters == changed for part in second.parts))
        self.assertTrue(all(part.parameters.pitch == 0.4 for part in first.parts))

    def test_cached_hip_triangle_is_not_accepted_for_gable(self):
        footprint = normalize_footprint([(0, 0), (8, 0), (2, 6)])
        self.assertEqual(len(decompose(footprint, RoofParameters("hip")).parts), 1)
        with self.assertRaises(UnsupportedRoofError):
            decompose(footprint, RoofParameters("gable"))

    def test_same_polygon_with_subdivided_edges_retains_current_provenance(self):
        points = [(0, 0), (13, 0), (13, 4), (5, 4), (5, 11), (0, 11)]
        decompose(normalize_footprint(points))
        subdivided = []
        for a, b in zip(points, points[1:] + points[:1]):
            subdivided.extend([a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)])
        result = decompose(normalize_footprint(subdivided))
        originals = {
            i
            for part in result.parts
            for edge in part.source_edges
            for i in edge.original_edges
        }
        self.assertEqual(originals, set(range(len(subdivided))))

    def test_repeated_directions_preserve_unique_chords_and_partition_coverage(self):
        cases = json.loads(
            (Path(__file__).parent / "fixtures/roof_acceptance.json").read_text()
        )
        for name in ("orthogonal_L", "rotated_L", "oblique_L", "orthogonal_U"):
            footprint = normalize_footprint(
                next(c["footprint"] for c in cases if c["name"] == name)
            )
            points = polygon_ring(footprint.polygon)
            p = np.asarray(points)
            edges = np.roll(p, -1, axis=0) - p
            directions = edges / np.linalg.norm(edges, axis=1)[:, None]
            cuts = candidate_cuts(points, directions, minimum_vertices=4)
            repeated = candidate_cuts(
                points, np.vstack((directions, directions)), minimum_vertices=4
            )
            self.assertEqual(cuts, repeated)
            self.assertTrue(cuts)
            self.assertEqual(len(cuts), len({cut for cut, _ in cuts}))
            for cut, rings in cuts:
                polygons = [Polygon(ring) for ring in rings]
                self.assertTrue(all(p.is_valid for p in polygons))
                self.assertLess(
                    unary_union(polygons).symmetric_difference(footprint.polygon).area,
                    1e-10,
                )
                self.assertLess(polygons[0].intersection(polygons[1]).area, 1e-10)

    def test_quad_search_does_not_emit_triangular_cut_pieces(self):
        footprint = normalize_footprint(
            [(0, 0), (13, 0), (13, 4), (5, 4), (5, 11), (0, 11)]
        )
        p = np.asarray(footprint.polygon.exterior.coords)[:-1]
        edges = np.roll(p, -1, axis=0) - p
        directions = edges / np.linalg.norm(edges, axis=1)[:, None]
        cuts = candidate_cuts(
            polygon_ring(footprint.polygon),
            directions,
            minimum_vertices=4,
        )
        self.assertTrue(cuts)
        for _, pieces in cuts:
            for piece in pieces:
                self.assertGreaterEqual(len(piece), 4)
