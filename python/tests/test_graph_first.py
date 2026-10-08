# SPDX-License-Identifier: GPL-3.0-or-later
"""Primary topology/ownership proofs independent of any roof geometry solver."""

from dataclasses import replace
import python
import unittest
from roof_generator.core.provenance import BoundaryPoint
from roof_generator.core.graph import RoofFace, make_graph
from roof_generator.core.errors import UnsupportedRoofError


class GraphContractTests(unittest.TestCase):
    def graph(self):
        # Authored gable disk: two faces share one ridge, with two gable caps.
        points = ((0, 0), (12, 0), (12, 6), (0, 6), (0, 3), (12, 3))
        loops = (RoofFace((0, 1, 5, 4), (0,), (0,)), RoofFace((5, 2, 3, 4), (0,), (2,)))
        labels = {
            (0, 1): "eave",
            (2, 3): "eave",
            (0, 4): "gable_end",
            (3, 4): "gable_end",
            (1, 5): "gable_end",
            (2, 5): "gable_end",
            (4, 5): "ridge",
        }
        locations = {i: BoundaryPoint(i, 0) for i in range(4)}
        locations.update({4: BoundaryPoint(3, 0.5), 5: BoundaryPoint(1, 0.5)})
        return make_graph(
            points[:4],
            ((0,), (1,), (2,), (3,)),
            points,
            locations,
            ("corner",) * 4 + ("ridge_end",) * 2,
            loops,
            labels,
            "gable",
        )

    def test_authored_gable_contract_and_inspection(self):
        g = self.graph()
        view = g.inspect()
        self.assertEqual(view["features"], {"eave": 2, "gable_end": 4, "ridge": 1})
        self.assertEqual(view["face_adjacency"], [(0, 1)])
        self.assertEqual(len(g.vertices) - len(g.edges) + len(g.faces), 1)
        self.assertTrue(all(v.boundary is not None for v in g.vertices))
        self.assertEqual([f.eaves for f in g.faces], [(0,), (2,)])

    def test_incidence_and_boundary_faults_are_rejected(self):
        g = self.graph()
        with self.assertRaisesRegex(UnsupportedRoofError, "edge/face incidence"):
            replace(g, edges=(replace(g.edges[0], faces=()),) + g.edges[1:])
        with self.assertRaisesRegex(UnsupportedRoofError, "missing or duplicated"):
            replace(g, edges=g.edges[:-1])
        with self.assertRaisesRegex(UnsupportedRoofError, "provenance"):
            replace(
                g,
                edges=(
                    replace(
                        g.edges[0],
                        boundary=replace(g.edges[0].boundary, original_edges=(99,)),
                    ),
                )
                + g.edges[1:],
            )


if __name__ == "__main__":
    unittest.main()
