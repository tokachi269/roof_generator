# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent cell geometry/provenance oracles; no roof candidate evaluation."""

import math
import unittest
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from python.graph_first.footprint import analyze
from python.graph_first.cells import decompose
from python.graph_first.errors import UnsupportedRoofError

L = np.array([(0, 0), (14.2, 0), (14.2, 5.6), (5.2, 5.6), (5.2, 12.8), (0, 12.8)])


def cell_key(points):
    return tuple(sorted(tuple(np.round(p, 6)) for p in points))


class CellPartitionTests(unittest.TestCase):
    def test_minimum_two_cell_partition_and_explicit_adjacency(self):
        fp = analyze(L)
        d = decompose(fp)
        self.assertEqual((len(d.cells), len(d.adjacency)), (2, 1))
        self.assertEqual(d.certificate.minimum_cells, 2)
        self.assertEqual(len(d.certificate.selection.diagonals), 0)
        self.assertEqual(len(d.certificate.completions), 1)
        cells = {
            cell_key([fp.frame.world_xy(d.vertices[i]) for i in c.corners])
            for c in d.cells
        }
        expected = {
            cell_key([(0, 0), (5.2, 0), (5.2, 12.8), (0, 12.8)]),
            cell_key([(5.2, 0), (14.2, 0), (14.2, 5.6), (5.2, 5.6)]),
        }
        self.assertEqual(cells, expected)
        self.assertEqual(
            cell_key(
                [fp.frame.world_xy(d.vertices[i]) for i in d.adjacency[0].interval]
            ),
            cell_key([(5.2, 0), (5.2, 5.6)]),
        )
        self.assertEqual(d.adjacency[0].cells, (0, 1))
        self.assertEqual(sum(len(s.artificial) for c in d.cells for s in c.sides), 2)
        # Independent polygon oracle only in tests, not in partition selection.
        polygons = [
            Polygon([fp.frame.world_xy(d.vertices[i]) for i in c.boundary])
            for c in d.cells
        ]
        self.assertTrue(all(p.is_valid for p in polygons))
        self.assertLess(polygons[0].intersection(polygons[1]).area, 1e-8)
        self.assertLess(
            unary_union(polygons).symmetric_difference(Polygon(L)).area, 1e-8
        )
        for edge in range(len(fp.vertices)):
            spans = sorted(
                s.interval
                for c in d.cells
                for side in c.sides
                for s in side.exterior
                if s.edge == edge
            )
            self.assertAlmostEqual(spans[0][0], 0)
            self.assertAlmostEqual(spans[-1][1], 1)
            for a, b in zip(spans, spans[1:]):
                self.assertAlmostEqual(a[1], b[0])

    def test_cells_are_invariant_under_rigid_and_boundary_representations(self):
        angle = 0.817
        r = np.array(
            [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
        )
        split = []
        for a, b in zip(L, np.roll(L, -1, axis=0)):
            split.extend((a, (a + b) / 2))
        variants = [
            (np.roll(L, 3, axis=0), np.eye(2), np.zeros(2)),
            (L[::-1], np.eye(2), np.zeros(2)),
            (L @ r.T + [147, -292], r, np.array([147, -292])),
            (split, np.eye(2), np.zeros(2)),
        ]
        expected = {
            cell_key([(0, 0), (5.2, 0), (5.2, 12.8), (0, 12.8)]),
            cell_key([(5.2, 0), (14.2, 0), (14.2, 5.6), (5.2, 5.6)]),
        }
        for points, rotation, offset in variants:
            fp = analyze(points)
            d = decompose(fp)
            world = (
                lambda ids: (
                    np.array([fp.frame.world_xy(d.vertices[i]) for i in ids]) - offset
                )
                @ rotation
            )
            self.assertEqual({cell_key(world(c.corners)) for c in d.cells}, expected)
            self.assertEqual(
                {
                    i
                    for c in d.cells
                    for s in c.sides
                    for span in s.exterior
                    for i in span.original_edges
                },
                set(range(len(points))),
            )

    def test_no_partition_tree_or_unsupported_continuation(self):
        d = decompose(analyze([(0, 0), (12, 0), (12, 6), (0, 6)]))
        self.assertEqual((len(d.cells), d.adjacency), (1, ()))
        self.assertEqual(d.certificate.minimum_cells, 1)
        # The formerly unsupported multi-reflex case now has its known
        # minimum partition; no L-only selector is involved.
        t = decompose(
            analyze(
                [(0, 0), (16, 0), (16, 5), (10, 5), (10, 12), (6, 12), (6, 5), (0, 5)]
            )
        )
        self.assertEqual((len(t.cells), len(t.adjacency)), (2, 1))
        self.assertEqual(t.certificate.minimum_cells, 2)
        with self.assertRaisesRegex(UnsupportedRoofError, "orthogonal"):
            decompose(analyze([(0, 0), (12, 0), (13, 4), (5, 4), (6, 10), (0, 10)]))


if __name__ == "__main__":
    unittest.main()
