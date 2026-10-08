# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
import xml.etree.ElementTree as ET
from python.inspect_architectural_parts import fixture, inspect, svg


class InspectionProof(unittest.TestCase):
    def test_all_requested_original_inputs_have_inspectable_parts_and_candidates(self):
        counts = {
            "orthogonal_U": (3, 4),
            "cross": (3, 2),
            "residential_multi_reflex": (4, 4),
            "grid_14": (5, 12),
            "grid_20": (7, 16),
            "grid_40": (12, 48),
        }
        for name, (minimum, options) in counts.items():
            data = inspect(fixture(name))
            self.assertEqual(data["summary"]["minimum_cells"], minimum)
            self.assertEqual(len(data["candidate_partitions"]), options)
            self.assertTrue(data["interpretation"]["search"]["complete"])
            self.assertTrue(data["interpretation"]["retained"])
            self.assertIsNone(data["interpretation"]["roof_topology"])
            for result in data["interpretation"]["retained"]:
                g = result["graph"]
                self.assertIsNone(g["roof_topology"])
                self.assertEqual(
                    sorted(c for p in g["parts"] for c in p["cells"]),
                    list(range(minimum)),
                )
            xml = ET.fromstring(svg(data))
            self.assertEqual(xml.tag, "{http://www.w3.org/2000/svg}svg")
            self.assertIn("No roof primitives", svg(data))
            self.assertIn("All retained ArchitecturalPart graphs", svg(data))

    def test_inspection_never_promotes_incomplete_search(self):
        data = inspect(fixture("orthogonal_U"), max_work=1)
        self.assertEqual(data["summary"]["status"], "incomplete")
        self.assertEqual(data["interpretation"]["retained"], [])
        ET.fromstring(svg(data))

    def test_relations_and_consumed_boundaries_are_exposed_separately(self):
        data = inspect(fixture("residential_multi_reflex"))
        g = data["interpretation"]["retained"][0]["graph"]
        self.assertEqual(sum(len(p["consumed"]) for p in g["parts"]), 2)
        self.assertEqual(len(g["adjacency"]), 1)
        self.assertEqual(len(g["relations"]), 3)
        self.assertTrue(g["issues"])
        self.assertIn("conditional when marked ?", svg(data))


if __name__ == "__main__":
    unittest.main()
