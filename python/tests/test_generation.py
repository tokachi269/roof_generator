# SPDX-License-Identifier: GPL-3.0-or-later
import python
import unittest
from roof_generator.core.generation import (
    generate_roof,
    prepare_generation,
    GenerationSettings,
)
from roof_generator.core.errors import UnsupportedRoofError
from python.inspect_architectural_parts import fixture


class GenerationProof(unittest.TestCase):
    def test_single_entry_produces_four_rectangle_meshes(self):
        for kind in ("gable", "hip", "shed", "flat"):
            result = generate_roof(
                ((0, 0), (12, 0), (12, 6), (0, 6)),
                GenerationSettings(kind, eave_height=2),
            )
            self.assertIs(result.mesh.graph, result.generation.selected.graph)
            self.assertTrue(result.mesh.faces)
            self.assertEqual(
                result.generation.geometry_problem.faces, result.mesh.faces
            )

    def test_compound_problem_is_distinct_from_completed_mesh(self):
        raw = fixture("cross")["footprint"]
        g = prepare_generation(raw)
        self.assertEqual(len(g.candidates.valid), 2)
        self.assertTrue(g.geometry_problem.variable_xy)
        with self.assertRaisesRegex(UnsupportedRoofError, "analytic solve supports"):
            generate_roof(raw)

    def test_flat_compound_consumes_all_cuts_without_pitched_prior(self):
        for name in (
            "orthogonal_U",
            "cross",
            "residential_multi_reflex",
            "grid_14",
            "grid_20",
            "grid_40",
        ):
            r = generate_roof(
                fixture(name)["footprint"],
                GenerationSettings("flat", pitch=0, eave_height=3),
            )
            self.assertEqual(len(r.mesh.faces), 1)
            self.assertTrue(all(e.boundary is not None for e in r.mesh.graph.edges))
            self.assertTrue(
                all(
                    p[2] == 3 / r.generation.footprint.frame.scale
                    for p in r.mesh.vertices
                )
            )
            self.assertEqual(
                r.mesh.graph.faces[0].cells,
                tuple(range(len(r.generation.selected.architecture.members))),
            )


if __name__ == "__main__":
    unittest.main()
