# SPDX-License-Identifier: GPL-3.0-or-later
import python
import gzip
import json
from pathlib import Path
import unittest
from shapely.geometry import Polygon
from python.audit_coverage import inspect


class CoverageAuditTests(unittest.TestCase):
    def test_frozen_categories_are_simple_and_nonuniform_is_not_uniform_scaling(self):
        p = Path(__file__).parents[1] / "docs/canonical/coverage_inputs_v1.json.gz"
        data = json.loads(gzip.decompress(p.read_bytes()))
        self.assertEqual(data["version"], 1)
        self.assertEqual(len(data["corpora"]), 6)
        for category, records in data["corpora"].items():
            for r in records:
                poly = Polygon(r["footprint"])
                self.assertTrue(poly.is_valid and poly.area > 0, (category, r["name"]))
        intervals = sorted(
            {p[0] for p in data["corpora"]["nonuniform_orthogonal"][0]["footprint"]}
        )
        self.assertGreater(
            len({round(b - a, 5) for a, b in zip(intervals, intervals[1:])}), 1
        )

    def test_valid_oblique_input_is_partition_failure_not_invalid_footprint(self):
        row = inspect(
            {
                "name": "probe",
                "footprint": [(0, 0), (12, 0), (13, 4), (5, 4), (6, 10), (0, 10)],
            }
        )
        self.assertTrue(row["success"]["footprint"])
        self.assertFalse(row["success"]["partition"])
        self.assertEqual(row["failure_owner"], "partition")
        self.assertFalse(row["Blender_measured"])

    def test_graph_is_not_final_mesh_support(self):
        from python.inspect_architectural_parts import fixture

        row = inspect(dict(fixture("orthogonal_U"), name="U"))
        self.assertTrue(row["success"]["GeometryProblem"])
        self.assertTrue(row["success"]["mesh"])
        self.assertFalse(row["success"]["Blender"])
