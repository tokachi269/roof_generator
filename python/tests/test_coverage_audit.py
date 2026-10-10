# SPDX-License-Identifier: GPL-3.0-or-later
import python
from dataclasses import replace
import gzip
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from shapely.geometry import Polygon
from python.audit_coverage import inspect


class CoverageAuditTests(unittest.TestCase):
    def test_wavefront_budget_is_incomplete_not_a_negative_roof_proof(self):
        from roof_generator.core.wavefront import WavefrontBudget
        with patch('python.audit_coverage.polygon_candidates',
                   side_effect=WavefrontBudget('roof wavefront work budget exhausted')):
            row = inspect({'name': 'bounded', 'footprint': ((0, 0), (12, 0), (12, 6), (0, 6))})
        self.assertTrue(row['success']['footprint'])
        self.assertTrue(row['incomplete_search'])
        self.assertEqual(row['failure_owner'], 'search')
        self.assertEqual(row['failure']['code'], 'incomplete_search')
        self.assertFalse(row['success']['mesh'])

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

    def test_valid_oblique_uses_polygon_model_without_rectangle_partition(self):
        row = inspect(
            {
                "name": "probe",
                "footprint": [(0, 0), (12, 0), (13, 4), (5, 4), (6, 10), (0, 10)],
            }
        )
        self.assertTrue(row["success"]["footprint"])
        self.assertTrue(row["success"]["partition"])
        self.assertFalse(row['partition_required'])
        self.assertEqual(row['partition_count'],0)
        self.assertTrue(row['success']['mesh'])
        self.assertIsNone(row['failure_owner'])
        self.assertFalse(row["Blender_measured"])

    def test_oblique_without_opposed_caps_is_architecture_failure(self):
        row=inspect({'name':'nonparallel','footprint':[(0,0),(12,0),(13.2,4),(5,4.7),(6.8,10),(2,9.3)]})
        self.assertTrue(row['success']['footprint'])
        self.assertTrue(row['success']['partition'])
        self.assertFalse(row['partition_required'])
        self.assertEqual(row['terminal_domain']['opposed_edges'],())
        self.assertEqual(row["failure_owner"], "architecture")
        self.assertEqual(row["failure"]["code"], "no_valid_candidate")
        self.assertFalse(row["Blender_measured"])

    def test_angle_inputs_are_frozen_simple_and_roof_type_is_observed(self):
        from python.generate_angle_corpus import corpus
        path=Path(__file__).parents[1]/'docs/canonical/angle_inputs_v1.json.gz'
        stored=json.loads(gzip.decompress(path.read_bytes()))
        self.assertEqual(stored,json.loads(json.dumps(corpus())))
        for category,records in stored['corpora'].items():
            for record in records:
                polygon=Polygon(record['footprint'])
                self.assertTrue(polygon.is_valid and polygon.area>0,(category,record['name']))
        record=stored['corpora']['oblique_acceptance_hip'][0]
        result=inspect(record)
        self.assertEqual(result['roof_type'],'hip')
        self.assertTrue(result['success']['mesh'])
        self.assertFalse(result['partition_required'])

    def test_graph_is_not_final_mesh_support(self):
        from python.inspect_architectural_parts import fixture

        row = inspect(dict(fixture("orthogonal_U"), name="U"))
        self.assertTrue(row["success"]["GeometryProblem"])
        self.assertTrue(row["success"]["mesh"])
        self.assertFalse(row["success"]["Blender"])

    def test_mesh_rejection_is_owned_by_mesh_not_solve(self):
        from roof_generator.core.errors import UnsupportedRoofError

        with patch("python.audit_coverage.RoofMesh", side_effect=UnsupportedRoofError("mesh proof")):
            row = inspect({"name": "rectangle", "footprint": ((0, 0), (12, 0), (12, 6), (0, 6))})
        self.assertTrue(row["success"]["solve"])
        self.assertFalse(row["success"]["mesh"])
        self.assertEqual(row["failure_owner"], "mesh")

    def test_incomplete_search_does_not_hide_graph_existence_or_select_seed(self):
        from roof_generator.core.generation import prepare_generation

        raw = ((0, 0), (12, 0), (12, 6), (0, 6))
        pool = replace(prepare_generation(raw).candidates, complete=False, reason="budget")
        with patch("python.audit_coverage.polygon_candidates", return_value=pool):
            row = inspect({"name": "incomplete", "footprint": raw})
        self.assertTrue(row["success"]["RoofGraph"])
        self.assertTrue(row["success"]["GeometryProblem"])
        self.assertFalse(row["success"]["solve"])
        self.assertNotIn("selected_id", row)
        self.assertEqual(row["failure"]["code"], "incomplete_search")

    def test_supplemental_branch_network_inputs_are_frozen_and_simple(self):
        from python.branch_network_corpus import corpus

        p = Path(__file__).parents[1] / "docs/canonical/branch_network_inputs_v1.json.gz"
        stored = json.loads(gzip.decompress(p.read_bytes()))
        self.assertEqual(stored, json.loads(json.dumps(corpus())))
        rows = stored["corpora"]["structured_branch_network"]
        self.assertEqual(len(rows), 100)
        for row in rows:
            polygon = Polygon(row["footprint"])
            self.assertTrue(polygon.is_valid and polygon.area > 0)
