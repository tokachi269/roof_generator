# SPDX-License-Identifier: GPL-3.0-or-later
"""Classical partition proof with independent geometry/combinatorial oracles."""

from itertools import combinations
import unittest
from shapely.geometry import Polygon, LineString
from python.graph_first.footprint import analyze
from python.graph_first.rectangle_partition import (
    good_diagonals,
    select_diagonals,
    maximum_matching,
    independent_set,
    partition,
    corners,
)

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


class MatchingTests(unittest.TestCase):
    def test_cross_shared_endpoints_are_conflicts(self):
        f = analyze(CROSS)
        s = select_diagonals(f, good_diagonals(f))
        self.assertEqual(
            (len(s.diagonals), len(s.conflicts), len(s.matching), len(s.selected)),
            (4, 4, 2, 2),
        )
        # All four conflicts meet at original reflex endpoints, not at a proper
        # interior crossing. Omitting closed endpoint conflicts breaks optimum.
        self.assertTrue(
            all(
                set(s.diagonals[a].endpoints).intersection(s.diagonals[b].endpoints)
                for a, b in s.conflicts
            )
        )

    def test_all_three_by_three_graphs_match_exhaustive_independent_sets(self):
        left = (0, 1, 2)
        right = (3, 4, 5)
        possible = tuple((a, b) for a in left for b in right)
        for mask in range(1 << 9):
            edges = tuple(e for i, e in enumerate(possible) if mask & (1 << i))
            matching = maximum_matching(left, right, edges)
            selected = independent_set(left, right, edges, matching)
            # Independent exhaustive graph oracle, not augmenting paths.
            best = max(
                sum(bool(subset & (1 << i)) for i in range(6))
                for subset in range(1 << 6)
                if all(not (subset & (1 << a) and subset & (1 << b)) for a, b in edges)
            )
            self.assertEqual(len(selected), best)
            self.assertEqual(len(matching), 6 - best)
            self.assertEqual(len({a for a, b in matching}), len(matching))
            self.assertEqual(len({b for a, b in matching}), len(matching))
            self.assertTrue(all(e in edges for e in matching))


class SubdivisionTests(unittest.TestCase):
    def test_literal_minimum_counts_and_independent_geometry(self):
        from shapely.ops import unary_union

        cases = [
            ([(0, 0), (12, 0), (12, 6), (0, 6)], 1),
            ([(0, 0), (14.2, 0), (14.2, 5.6), (5.2, 5.6), (5.2, 12.8), (0, 12.8)], 2),
            (T, 2),
            (U, 3),
            (CROSS, 3),
        ]
        for points, minimum in cases:
            with self.subTest(points=points):
                fp = analyze(points)
                result = partition(fp)
                self.assertEqual(len(result.faces), minimum)
                polygons = [
                    Polygon([result.vertices[i] for i in f]) for f in result.faces
                ]
                self.assertTrue(all(p.is_valid and p.area > 0 for p in polygons))
                self.assertLess(
                    unary_union(polygons)
                    .symmetric_difference(Polygon(fp.vertices))
                    .area,
                    1e-10,
                )
                self.assertLess(
                    abs(sum(p.area for p in polygons) - Polygon(fp.vertices).area),
                    1e-10,
                )
                self.assertTrue(
                    all(len(corners(f, result.vertices)) == 4 for f in result.faces)
                )
                incident = {e.vertices: [] for e in result.edges}
                for index, f in enumerate(result.faces):
                    for a, b in zip(f, f[1:] + f[:1]):
                        incident[tuple(sorted((a, b)))].append(index)
                self.assertTrue(
                    all(
                        len(incident[e.vertices])
                        == (1 if e.boundary is not None else 2)
                        for e in result.edges
                    )
                )


class CellRecordTests(unittest.TestCase):
    def test_generic_records_cover_provenance_and_every_shared_interval(self):
        from collections import Counter
        from python.graph_first.cells import decompose

        for points, minimum in [(T, 2), (U, 3), (CROSS, 3)]:
            fp = analyze(points)
            d = decompose(fp)
            self.assertEqual(len(d.cells), minimum)
            self.assertEqual(d.certificate.minimum_cells, minimum)
            incidence = Counter(
                cut for c in d.cells for s in c.sides for cut in s.artificial
            )
            self.assertTrue(all(count == 2 for count in incidence.values()))
            self.assertEqual(set(incidence), {a.interval for a in d.adjacency})
            self.assertEqual(len(d.adjacency), len(incidence))
            for a in d.adjacency:
                for cell, side in zip(a.cells, a.sides):
                    self.assertIn(a.interval, d.cells[cell].sides[side].artificial)
            self.assertEqual(
                {
                    i
                    for c in d.cells
                    for s in c.sides
                    for e in s.exterior
                    for i in e.original_edges
                },
                set(range(len(points))),
            )
            self.assertTrue(
                all(len(c.corners) == 4 and len(c.sides) == 4 for c in d.cells)
            )

    def test_generic_two_cell_partition_supplies_existing_terminal_graft(self):
        from python.graph_first.cells import decompose
        from python.graph_first.topology import compose
        from python.tests.test_graph_first_cells import L
        from python.tests.test_graph_first_connection import assert_terminal

        fp = analyze(L)
        d = decompose(fp)
        self.assertEqual((len(d.cells), len(d.adjacency)), (2, 1))
        assert_terminal(self, fp, compose(d))


if __name__ == "__main__":
    unittest.main()
