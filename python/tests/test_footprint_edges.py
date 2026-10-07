# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import math
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "addon"))
from roof_generator.core.roof_geometry import normalize_footprint
from roof_generator.core.roof_building import generate_roof


class FootprintEdgeTests(unittest.TestCase):
    def test_five_degree_threshold_and_source_edges(self):
        for turn, count in ((4.9, 4), (5, 4), (5.1, 5), (-4.9, 4), (-5, 4), (-5.1, 5)):
            with self.subTest(turn=turn):
                points = [(0, 0), (1, 0), (2, math.tan(math.radians(turn))), (2, 2), (0, 2)]
                footprint = normalize_footprint(points)
                self.assertEqual(len(footprint.source_edges), count)
                self.assertEqual(sorted(i for group in footprint.source_edges for i in group), list(range(5)))
                if count == 4:
                    self.assertIn((0, 1), footprint.source_edges)

    def test_right_angle_grid_corners_remain(self):
        footprint = normalize_footprint([(0, 0), (1, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)])
        self.assertEqual(len(footprint.source_edges), 6)
        self.assertIn((0, 1), footprint.source_edges)

    def test_roof_uses_merged_outline_and_preserves_input(self):
        points = np.array([(0, 0), (2, -0.05), (4, 0), (4, 3), (0, 3)], dtype=float)
        original = points.copy()
        roof = generate_roof(points)
        self.assertEqual(len(roof.footprint.source_edges), 4)
        self.assertEqual(len(roof.decomposition.parts), 1)
        np.testing.assert_array_equal(points, original)
        np.testing.assert_allclose(np.asarray(roof.mesh.vertices)[:, :2].min(axis=0), (0, 0), atol=1e-8)

    def test_orientation_and_metric_transforms(self):
        points = np.array([(0, 0), (2, -0.05), (4, 0), (4, 3), (0, 3)])
        for reverse in (False, True):
            for start in range(5):
                p = np.roll(points[::-1] if reverse else points, start, axis=0)
                for scale in (0.01, 1, 1000):
                    footprint = normalize_footprint(p * scale + (147.3, -239.7))
                    self.assertEqual(len(footprint.source_edges), 4)
                    self.assertEqual(sorted(i for group in footprint.source_edges for i in group), list(range(5)))
                    self.assertEqual(sorted(map(len, footprint.source_edges)), [1, 1, 1, 2])


if __name__ == "__main__":
    unittest.main()
