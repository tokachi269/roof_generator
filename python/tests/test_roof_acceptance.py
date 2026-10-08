# SPDX-License-Identifier: GPL-3.0-or-later
"""Current capability boundary and independent mesh/projection invariants."""

import python
from dataclasses import replace
import json
from pathlib import Path
import unittest
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from roof_generator.core.generation import (
    generate_roof,
    prepare_generation,
    GenerationSettings,
)
from roof_generator.core.errors import UnsupportedRoofError
from python.tests.test_roof_harness import assert_disk, world_mesh

FIXTURES = Path(__file__).parent / "fixtures/roof_acceptance.json"


class RoofAcceptanceTests(unittest.TestCase):
    def test_original_inputs_have_explicit_mesh_and_topology_capabilities(self):
        mesh_supported = {
            "rectangle_gable",
            "rectangle_hip",
            "rectangle_shed",
            "rotated_rectangle",
        }
        topology_supported = mesh_supported | {
            "orthogonal_L",
            "orthogonal_T",
            "rotated_L",
            "unequal_width_join",
            "terminating_ridge",
            "valley_join",
        }
        for row in json.loads(FIXTURES.read_text()):
            settings = GenerationSettings(row["roof_type"], row["pitch"])
            raw = row["footprint"]
            with self.subTest(case=row["name"]):
                if row["name"] in topology_supported:
                    p = prepare_generation(raw, settings)
                    self.assertTrue(p.candidates.valid)
                    self.assertEqual(
                        p.geometry_problem.faces,
                        tuple(f.loop for f in p.selected.graph.faces),
                    )
                else:
                    with self.assertRaises(UnsupportedRoofError):
                        prepare_generation(raw, settings)
                if row["name"] in mesh_supported:
                    r = generate_roof(raw, settings)
                    assert_disk(self, world_mesh(r))
                else:
                    with self.assertRaises(UnsupportedRoofError):
                        generate_roof(raw, settings)

    def test_four_types_have_exact_coverage_planarity_and_no_internal_faces(self):
        raw = ((0, 0), (13.6, 0), (13.6, 8.4), (0, 8.4))
        for kind in ("gable", "hip", "shed", "flat"):
            result = generate_roof(raw, GenerationSettings(kind, eave_height=2))
            mesh = world_mesh(result)
            assert_disk(self, mesh)
            polys = []
            for face in mesh.faces:
                p = np.asarray([mesh.vertices[i] for i in face])
                poly = Polygon(p[:, :2])
                polys.append(poly)
                self.assertTrue(poly.is_valid)
                self.assertGreater(poly.area, 0)
                self.assertLess(
                    np.linalg.svd(p - p.mean(axis=0), compute_uv=False)[-1], 1e-8
                )
            self.assertLess(
                unary_union(polys).symmetric_difference(Polygon(raw)).area, 1e-8
            )
            self.assertAlmostEqual(
                sum(p.area for p in polys), Polygon(raw).area, places=8
            )
            self.assertEqual(
                generate_roof(raw, GenerationSettings(kind, eave_height=2)), result
            )

    def test_flat_original_orthogonal_concave_inputs_are_one_clean_face(self):
        names = {
            "orthogonal_L",
            "orthogonal_T",
            "orthogonal_U",
            "unequal_width_join",
            "terminating_ridge",
            "valley_join",
            "residential_multi_reflex",
        }
        for row in json.loads(FIXTURES.read_text()):
            if row["name"] not in names:
                continue
            r = generate_roof(row["footprint"], GenerationSettings("flat"))
            assert_disk(self, world_mesh(r))
            self.assertEqual(len(r.mesh.faces), 1)
            self.assertTrue(
                all(e.kind == "eave" and e.boundary for e in r.mesh.graph.edges)
            )

    def test_validation_rejects_coordinate_and_incidence_faults(self):
        r = generate_roof(((0, 0), (12, 0), (12, 6), (0, 6)), GenerationSettings("hip"))
        mesh = r.mesh
        graph = mesh.graph
        for faces in (
            graph.faces + (graph.faces[0],),
            graph.faces[:-1],
            (replace(graph.faces[0], loop=(0, 1, 999)),) + graph.faces[1:],
            (replace(graph.faces[0], loop=graph.faces[0].loop[::-1]),)
            + graph.faces[1:],
        ):
            with self.assertRaises(UnsupportedRoofError):
                replace(graph, faces=faces)
        for coordinates in (mesh.vertices + (mesh.vertices[0],), mesh.vertices[:-1]):
            with self.assertRaises(UnsupportedRoofError):
                replace(mesh, vertices=coordinates)
        xyz = list(mesh.vertices)
        xyz[4] = (*xyz[4][:2], xyz[4][2] + 0.02)
        with self.assertRaises(UnsupportedRoofError):
            replace(mesh, vertices=tuple(xyz))

    def test_invalid_input_and_search_limits_are_explicit(self):
        for raw in (
            ((0, 0), (2, 2), (0, 2), (2, 0)),
            ((0, 0), (2, 0), (2, 0), (0, 2)),
            ((0, 0), (1, 0), (2, 0)),
        ):
            with self.assertRaises(UnsupportedRoofError):
                prepare_generation(raw)
        row = next(
            r for r in json.loads(FIXTURES.read_text()) if r["name"] == "orthogonal_L"
        )
        with self.assertRaises(UnsupportedRoofError):
            prepare_generation(row["footprint"], GenerationSettings(max_work=1))
        with self.assertRaises(ValueError):
            GenerationSettings(pitch=0)


if __name__ == "__main__":
    unittest.main()
