# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent finite MIS and unit-grid exact-cover proofs of alternatives."""

import itertools
import json
import math
from functools import lru_cache
from pathlib import Path
import python
import unittest
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose
from roof_generator.core.partition_candidates import candidates, maximum_sets, signature
from roof_generator.core.partition import Diagonal, Selection, maximum_matching
from python.tests.grid_footprints import outline as boundary


def tilings(cells):
    """Test-only exhaustive rectangle cover; no production partition helpers."""
    points = sorted(cells)
    ids = {p: i for i, p in enumerate(points)}
    rects = []
    for x in range(min(p[0] for p in points), max(p[0] for p in points) + 1):
        for y in range(min(p[1] for p in points), max(p[1] for p in points) + 1):
            for xx in range(x + 1, max(p[0] for p in points) + 2):
                for yy in range(y + 1, max(p[1] for p in points) + 2):
                    occupied = {(a, b) for a in range(x, xx) for b in range(y, yy)}
                    if occupied <= cells:
                        rects.append(
                            (sum(1 << ids[p] for p in occupied), (x, y, xx, yy))
                        )

    @lru_cache(None)
    def cover(mask):
        if not mask:
            return (frozenset(),)
        first = mask & -mask
        options = []
        for bits, rect in rects:
            if bits & first and bits & mask == bits:
                options.extend(s.union((rect,)) for s in cover(mask ^ bits))
        minimum = min(map(len, options))
        return tuple(set(s for s in options if len(s) == minimum))

    return set(cover((1 << len(points)) - 1))


def world_rectangles(d):
    result = []
    for c in d.cells:
        ps = [d.footprint.frame.world_xy(d.vertices[i]) for i in c.corners]
        result.append(
            tuple(
                round(v, 6)
                for v in (
                    min(p[0] for p in ps),
                    min(p[1] for p in ps),
                    max(p[0] for p in ps),
                    max(p[1] for p in ps),
                )
            )
        )
    return frozenset(result)


class MinimumCandidateProof(unittest.TestCase):
    def test_all_maximum_sets_on_every_three_by_three_conflict_graph(self):
        possible = tuple(itertools.product(range(3), range(3, 6)))
        for mask in range(1 << len(possible)):
            edges = tuple(e for i, e in enumerate(possible) if mask & (1 << i))
            valid = [
                frozenset(i for i in range(6) if bits & (1 << i))
                for bits in range(64)
                if all(not (bits & (1 << a) and bits & (1 << b)) for a, b in edges)
            ]
            n = max(map(len, valid))
            expected = {s for s in valid if len(s) == n}
            matching = maximum_matching((0, 1, 2), (3, 4, 5), edges)
            s = Selection(
                tuple(Diagonal((i, i + 6), int(i >= 3)) for i in range(6)),
                edges,
                matching,
                (),
            )
            self.assertEqual({frozenset(v) for v in maximum_sets(s)}, expected)

    def test_candidates_match_independent_small_minimum_tilings(self):
        domains = [
            {(0, 0), (1, 0), (0, 1)},
            {(x, y) for x in range(3) for y in range(3)} - {(1, 1), (1, 2)},
            {(1, 0), (0, 1), (1, 1), (2, 1), (1, 2)},
        ]
        for cells in domains:
            result = candidates(analyze(boundary(cells)))
            self.assertTrue(result.complete)
            self.assertEqual(
                {world_rectangles(d) for d in result.candidates}, tilings(cells)
            )
            original = decompose(analyze(boundary(cells)))
            self.assertIn(
                signature(original), {signature(d) for d in result.candidates}
            )

    def test_original_cases_keep_minimum_and_cover_exactly(self):
        from shapely.geometry import Polygon
        from shapely.ops import unary_union

        rows = json.loads(
            Path("python/tests/fixtures/rectangle_partition.json").read_text()
        )
        for row in rows:
            if row["name"] in ("comb_40", "staircase_20"):
                continue
            fp = analyze(row["footprint"])
            result = candidates(fp)
            self.assertTrue(result.complete, row["name"])
            for d in result.candidates:
                self.assertEqual(len(d.cells), row["minimum_cells"])
                pieces = [Polygon([d.vertices[i] for i in c.corners]) for c in d.cells]
                self.assertLess(
                    unary_union(pieces).symmetric_difference(Polygon(fp.vertices)).area,
                    1e-12,
                )
                self.assertLess(
                    sum(p.area for p in pieces) - unary_union(pieces).area, 1e-12
                )

    def test_work_and_candidate_limits_report_incomplete(self):
        fp = analyze(((0, 0), (5, 0), (5, 2), (2, 2), (2, 5), (0, 5)))
        for kwargs in ({"max_work": 1}, {"max_candidates": 1}):
            result = candidates(fp, **kwargs)
            self.assertFalse(result.complete)
            self.assertIn("recommendation unavailable", result.reason)
            self.assertTrue(result.candidates)
            self.assertTrue(all(len(d.cells) == 2 for d in result.candidates))

    def test_candidate_family_is_invariant_as_a_set(self):
        points = (
            (0, 0),
            (17.4, 0),
            (17.4, 13.2),
            (12, 13.2),
            (12, 5.2),
            (5.4, 5.2),
            (5.4, 13.2),
            (0, 13.2),
        )
        baseline = candidates(analyze(points))
        sig = sorted(signature(d) for d in baseline.candidates)
        a = 0.371
        c, s = math.cos(a), math.sin(a)
        for variant in (
            points[3:] + points[:3],
            tuple(reversed(points)),
            tuple((13 + c * x - s * y, -7 + s * x + c * y) for x, y in points),
            points[:1] + ((8.7, 0),) + points[1:],
        ):
            result = candidates(analyze(variant))
            self.assertTrue(result.complete)
            self.assertEqual(sorted(signature(d) for d in result.candidates), sig)


if __name__ == "__main__":
    unittest.main()
