# SPDX-License-Identifier: GPL-3.0-or-later
"""Candidate gates and physical seeded alternatives, independent of old core."""

from collections import Counter
from dataclasses import replace
import math
import unittest
from python.graph_first.footprint import analyze
from python.graph_first.partition_candidates import candidates
from python.graph_first.part_selection import recommend
from python.graph_first.topology_candidates import build_candidates
from python.graph_first.errors import UnsupportedRoofError
from python.inspect_architectural_parts import fixture


def pool(raw, direction=(1, 0), **budgets):
    return build_candidates(
        recommend(candidates(analyze(raw))), reference_direction=direction, **budgets
    )


class TopologyCandidateProof(unittest.TestCase):
    def test_valid_ambiguity_and_unsupported_are_different(self):
        cross = pool(fixture("cross")["footprint"])
        self.assertEqual(len(cross.valid), 2)
        self.assertEqual(len({cross.select(seed).id for seed in range(40)}), 2)
        for c in cross.valid:
            self.assertEqual(
                Counter(e.kind for e in c.graph.edges if len(e.faces) == 2),
                {"ridge": 4, "valley": 4},
            )
            self.assertEqual(len(c.graph.faces), 8)
            self.assertEqual(
                len({v for e in c.graph.edges for v in e.vertices})
                - len(c.graph.edges)
                + len(c.graph.faces),
                1,
            )
        for name in (
            "orthogonal_U",
            "residential_multi_reflex",
            "grid_14",
            "grid_20",
            "grid_40",
        ):
            result = pool(fixture(name)["footprint"])
            self.assertFalse(result.valid)
            self.assertTrue(result.rejected)
            for seed in (0, 1, 79):
                with self.assertRaisesRegex(UnsupportedRoofError, "no selectable"):
                    result.select(seed)

    def test_square_axis_is_real_roof_variation(self):
        result = pool(((0, 0), (6, 0), (6, 6), (0, 6)))
        self.assertEqual(len(result.valid), 2)
        ridges = {
            tuple(
                sorted(
                    c.graph.vertices[v].seed
                    for e in c.graph.edges
                    if e.kind == "ridge"
                    for v in e.vertices
                )
            )
            for c in result.valid
        }
        self.assertEqual(len(ridges), 2)
        self.assertEqual(len({result.select(seed).id for seed in range(40)}), 2)
        self.assertEqual(
            result.select(5), replace(result, valid=result.valid[::-1]).select(5)
        )

    def test_seeded_candidates_correspond_physically_under_metamorphisms(self):
        angle = 0.618
        c, s = math.cos(angle), math.sin(angle)
        for raw in (
            fixture("cross")["footprint"],
            fixture("orthogonal_L")["footprint"],
            [(0, 0), (8, 0), (8, 8), (0, 8)],
        ):
            raw = tuple(tuple(p) for p in raw)
            expected = pool(raw)
            midpoint = tuple((raw[0][k] + raw[1][k]) / 2 for k in (0, 1))
            for points, direction in (
                (raw[::-1], (1, 0)),
                (raw[2:] + raw[:2], (1, 0)),
                (raw[:1] + (midpoint,) + raw[1:], (1, 0)),
                (
                    tuple((c * x - s * y + 26, s * x + c * y - 41) for x, y in raw),
                    (c, s),
                ),
            ):
                result = pool(points, direction)
                self.assertEqual(
                    {x.id for x in expected.valid}, {x.id for x in result.valid}
                )
                for seed in (0, 1, 17):
                    self.assertEqual(expected.select(seed).id, result.select(seed).id)

    def test_geometry_fault_and_incomplete_search_never_reach_seed_choice(self):
        result = pool(((0, 0), (9, 0), (9, 5), (0, 5)))
        candidate = result.valid[0]
        with self.assertRaisesRegex(UnsupportedRoofError, "changes topology"):
            replace(candidate, geometry=replace(candidate.geometry, faces=()))
        result = pool(fixture("cross")["footprint"], max_axis_assignments=1)
        self.assertFalse(result.complete)
        with self.assertRaises(UnsupportedRoofError):
            result.select(3)
        search = candidates(analyze(fixture("cross")["footprint"]), max_work=1)
        result = build_candidates(recommend(search))
        self.assertFalse(result.complete)
        self.assertFalse(result.valid)


if __name__ == "__main__":
    unittest.main()
