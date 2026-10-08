# SPDX-License-Identifier: GPL-3.0-or-later
"""Classical partition proof with independent geometry/combinatorial oracles."""

from itertools import combinations
import unittest
from shapely.geometry import Polygon, LineString
from python.graph_first.footprint import analyze
from python.graph_first.rectangle_partition import good_diagonals

CROSS = [
    (1, 0),
    (2, 0),
    (2, 1),
    (3, 1),
    (3, 2),
    (2, 2),
    (2, 3),
    (1, 3),
    (1, 2),
    (0, 2),
    (0, 1),
    (1, 1),
]
T = [(0, 0), (16, 0), (16, 5), (10, 5), (10, 12), (6, 12), (6, 5), (0, 5)]
U = [(0, 0), (16, 0), (16, 14), (11, 14), (11, 5), (5, 5), (5, 14), (0, 14)]


def oracle_diagonals(points):
    # Raw input, independent reflex detection and GEOS open-segment relation.
    shape = Polygon(points)
    reflex = []
    for i, b in enumerate(points):
        a, c = points[i - 1], points[(i + 1) % len(points)]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) < 0:
            reflex.append(i)
    diagonals = []
    for a, b in combinations(reflex, 2):
        p, q = points[a], points[b]
        if p[0] != q[0] and p[1] != q[1]:
            continue
        relation = LineString((p, q)).relate(shape)
        if relation[0] == "1" and relation[1] == "F" and relation[2] == "F":
            diagonals.append(tuple(sorted((tuple(p), tuple(q)))))
    return reflex, tuple(sorted(diagonals))


class DiagonalTests(unittest.TestCase):
    def test_all_open_interior_diagonals_match_independent_pair_oracle(self):
        for points, expected in [
            (CROSS, 4),
            (T, 1),
            (U, 0),
            ([(0, 0), (12, 0), (12, 6), (0, 6)], 0),
        ]:
            with self.subTest(points=points):
                fp = analyze(points)
                diagonals = good_diagonals(fp)
                actual = tuple(
                    sorted(
                        tuple(
                            sorted(
                                tuple(
                                    round(x, 8)
                                    for x in fp.frame.world_xy(fp.vertices[i])
                                )
                                for i in d.endpoints
                            )
                        )
                        for d in diagonals
                    )
                )
                self.assertEqual(actual, oracle_diagonals(points)[1])
                self.assertEqual(len(actual), expected)
                self.assertTrue(all(d.axis in (0, 1) for d in diagonals))

    def test_boundary_reflex_edge_and_long_boundary_contacts_are_not_diagonals(self):
        self.assertEqual(good_diagonals(analyze(U)), ())
        # Multiple collinear indentations: a longer boundary-to-boundary pair
        # cannot pass through another boundary point to become a good diagonal.
        points = [
            (0, 0),
            (9, 0),
            (9, 5),
            (8, 5),
            (8, 2),
            (6, 2),
            (6, 5),
            (5, 5),
            (5, 2),
            (3, 2),
            (3, 5),
            (2, 5),
            (2, 2),
            (0, 2),
        ]
        fp = analyze(points)
        self.assertEqual(len(good_diagonals(fp)), len(oracle_diagonals(points)[1]))


if __name__ == "__main__":
    unittest.main()
