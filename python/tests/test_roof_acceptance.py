from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from collections import Counter
import json
import sys
import unittest
import numpy as np
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "addon"))

from roof_generator.core.roof_building import generate_roof
from roof_generator.core.roof_geometry import (
    UnsupportedRoofError,
    normalize_footprint,
    EPS,
)
from roof_generator.core.roof_parts import RoofParameters, decompose
from roof_generator.core.roof_mesh import RoofMesh
from roof_generator.core.roof_validation import validate_mesh

FIXTURES = Path(__file__).parent / "fixtures" / "roof_acceptance.json"


def acceptance_cases():
    return json.loads(FIXTURES.read_text())


def compare(test, a, b):
    # Intrinsic frame removes the requested rigid transform. Mesh indexing,
    # planar-region incidence and geometric features must remain equivalent.
    test.assertEqual(a.normalized_mesh.faces, b.normalized_mesh.faces)
    test.assertEqual(a.normalized_mesh.edge_features, b.normalized_mesh.edge_features)
    test.assertEqual(len(a.decomposition.parts), len(b.decomposition.parts))
    np.testing.assert_allclose(
        a.normalized_mesh.vertices, b.normalized_mesh.vertices, atol=EPS * 20, rtol=0
    )


class RoofAcceptanceTests(unittest.TestCase):
    def test_all_sixteen_final_mesh_scenarios_and_invariances(self):
        cases = acceptance_cases()
        self.assertEqual(len(cases), 16)
        for case in cases:
            with self.subTest(case=case["name"]):
                p = np.asarray(case["footprint"], float)
                params = RoofParameters(case["roof_type"], pitch=case["pitch"])
                result = generate_roof(p, params)
                self.assertEqual(
                    len(result.decomposition.parts), case["expected_parts"]
                )
                for feature in case["features"]:
                    self.assertGreater(result.validation.features.get(feature, 0), 0)
                # An independent validator also checks the actual returned
                # metric mesh, not only its normalized topology.
                validate_mesh(
                    result.mesh,
                    Polygon(p),
                    tolerance=result.footprint.frame.scale * EPS * 20,
                )
                again = generate_roof(p, params)
                self.assertEqual(result.mesh, again.mesh)
                compare(self, result, generate_roof(p + [147.381, -293.126], params))
                for angle in [0.371, 1.123]:
                    matrix = np.array(
                        [
                            [np.cos(angle), -np.sin(angle)],
                            [np.sin(angle), np.cos(angle)],
                        ]
                    )
                    compare(self, result, generate_roof(p @ matrix.T, params))
                subdivided = []
                for a, b in zip(p, np.roll(p, -1, axis=0)):
                    subdivided.extend([a, a + (b - a) * 0.37, a + (b - a) * 0.81])
                compare(self, result, generate_roof(subdivided, params))

    def test_roof_geometry_supports_all_four_types_on_general_quads(self):
        for name in ["parallelogram", "trapezoid", "general_convex_quad"]:
            case = next(c for c in acceptance_cases() if c["name"] == name)
            for kind in ["flat", "gable", "hip", "shed"]:
                with self.subTest(name=name, kind=kind):
                    result = generate_roof(case["footprint"], RoofParameters(kind))
                    self.assertGreater(result.validation.faces, 0)
                    if kind == "gable":
                        self.assertEqual(result.validation.features.get("ridge"), 1)
                    if kind == "hip":
                        self.assertGreater(result.validation.features.get("hip", 0), 0)

    def test_flat_and_hip_concave_roofs(self):
        for name in ["orthogonal_L", "orthogonal_T", "orthogonal_U", "oblique_L"]:
            p = next(c["footprint"] for c in acceptance_cases() if c["name"] == name)
            for kind in ["flat", "hip"]:
                with self.subTest(name=name, kind=kind):
                    result = generate_roof(p, RoofParameters(kind))
                    self.assertGreater(result.validation.faces, 0)
                    if kind == "flat":
                        self.assertEqual(result.validation.faces, 1)
                        self.assertFalse(
                            set(result.validation.features) & {"ridge", "hip", "valley"}
                        )

    def test_sheared_nonorthogonal_parts(self):
        affine = np.array([[1.0, 0.18], [-0.07, 1.0]])
        for name in ["orthogonal_L", "orthogonal_T", "orthogonal_U"]:
            case = next(c for c in acceptance_cases() if c["name"] == name)
            p = np.asarray(case["footprint"]) @ affine.T
            for kind in ["gable", "hip", "flat"]:
                with self.subTest(name=name, kind=kind):
                    result = generate_roof(p, RoofParameters(kind))
                    self.assertEqual(
                        len(result.decomposition.parts), case["expected_parts"]
                    )
                    if kind == "gable":
                        self.assertGreater(
                            result.validation.features.get("valley", 0), 0
                        )

    def test_triangle_hip_and_separate_hole_tessellation(self):
        result = generate_roof([(0, 0), (8, 0), (2, 6)], RoofParameters("hip"))
        self.assertEqual(result.validation.features.get("hip"), 3)
        self.assertEqual(result.validation.features.get("ridge", 0), 0)
        from roof_generator.core.roof_connections import RoofTopology, RoofRegion
        from roof_generator.core.roof_planes import RoofPlane
        from roof_generator.core.roof_mesh import tessellate

        outer = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        inner = Polygon([(3, 3), (7, 3), (7, 7), (3, 7)])
        plane = RoofPlane((0.0, 0.0, 0.0), 0, None, 0.0)
        topology = RoofTopology(
            outer,
            (),
            (
                RoofRegion(outer.difference(inner), plane, (0,)),
                RoofRegion(inner, plane, (0,)),
            ),
            (),
        )
        mesh = tessellate(topology)
        validate_mesh(mesh, outer)
        self.assertNotIn("ridge", mesh.edge_features.values())
        self.assertNotIn("valley", mesh.edge_features.values())

    def test_terminating_ridge_meets_host_plane_below_host_ridge(self):
        case = next(c for c in acceptance_cases() if c["name"] == "terminating_ridge")
        result = generate_roof(case["footprint"])
        vertices = np.asarray(result.mesh.vertices)
        # Main width=6.8 -> ridge height 1.7. Annex width=4.4 -> 1.1.
        # Its ridge terminates where host north slope reaches 1.1: y=4.6.
        target = np.array([8.9, 4.6, 1.1])
        self.assertLess(np.min(np.linalg.norm(vertices - target, axis=1)), 1e-5)
        i = int(np.argmin(np.linalg.norm(vertices - target, axis=1)))
        incident = [tag for edge, tag in result.mesh.edge_features.items() if i in edge]
        self.assertIn("ridge", incident)
        self.assertEqual(incident.count("valley"), 2)
        self.assertFalse(
            any(np.linalg.norm(v - [8.9, 3.4, 1.7]) < 1e-5 for v in vertices)
        )

    def test_part_overrides_and_height_differences(self):
        p = next(
            c["footprint"] for c in acceptance_cases() if c["name"] == "orthogonal_T"
        )
        result = generate_roof(p, part_parameters={1: RoofParameters("hip", pitch=0.7)})
        self.assertGreater(result.validation.features.get("hip", 0), 0)
        with self.assertRaises(UnsupportedRoofError):
            generate_roof(
                p, part_parameters={1: RoofParameters("flat", eave_height=10)}
            )
        with self.assertRaisesRegex(UnsupportedRoofError, "nonexistent"):
            generate_roof(p, part_parameters={50: RoofParameters()})

    def test_adjacency_and_source_provenance(self):
        for name in ["orthogonal_L", "orthogonal_T", "orthogonal_U", "oblique_L"]:
            result = generate_roof(
                next(c["footprint"] for c in acceptance_cases() if c["name"] == name)
            )
            for part in result.decomposition.parts:
                self.assertTrue(part.geometry.convex)
                self.assertTrue(part.source_edges)
                for neighbor in part.neighbors:
                    self.assertTrue(
                        any(
                            n.part_id == part.id
                            for n in result.decomposition.parts[
                                neighbor.part_id
                            ].neighbors
                        )
                    )
                    self.assertTrue(neighbor.shared_boundary)
            originals = {
                i
                for part in result.decomposition.parts
                for edge in part.source_edges
                for i in edge.original_edges
            }
            self.assertEqual(originals, set(range(len(result.footprint.source_edges))))
        trap = generate_roof(
            next(c["footprint"] for c in acceptance_cases() if c["name"] == "trapezoid")
        )
        self.assertTrue(trap.decomposition.parts[0].geometry.one_parallel_pair)

    def test_rejects_invalid_inputs_and_exhausted_search(self):
        invalid = [
            [(0, 0), (1, 1), (0, 1), (1, 0)],
            [(0, 0), (1, 0), (1, 0), (0, 1)],
            [(0, 0), (1, 0), (2, 0)],
            [(0, 0), (float("nan"), 0), (0, 1)],
        ]
        for p in invalid:
            with self.subTest(p=p), self.assertRaises(UnsupportedRoofError):
                generate_roof(p)
        for params in [
            RoofParameters("dome"),
            RoofParameters(pitch=0),
            RoofParameters(pitch=-1),
            RoofParameters(pitch=float("inf")),
            RoofParameters(eave_pair=(0, 1)),
        ]:
            with self.subTest(params=params), self.assertRaises(UnsupportedRoofError):
                generate_roof([(0, 0), (12, 0), (12, 6), (0, 6)], params)
        p = next(
            c["footprint"] for c in acceptance_cases() if c["name"] == "orthogonal_L"
        )
        with self.assertRaisesRegex(UnsupportedRoofError, "exhausted"):
            generate_roof(p, max_states=1)

    def test_planar_mesh_projection_and_local_placement(self):
        from roof_generator.mesh_input import generate_footprint_mesh

        p = np.array(
            [(0.0, 0.0, 0.0), (12.0, 0.0, 0.0), (12.0, 6.0, 0.0), (0.0, 6.0, 0.0)]
        )
        angle = 0.43
        rotation = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, np.cos(angle), -np.sin(angle)],
                [0.0, np.sin(angle), np.cos(angle)],
            ]
        )
        anchor = np.array([1e6, -1e6, 12.0])
        source = p @ rotation.T + anchor
        result = generate_footprint_mesh(
            source, [(0, 1, 2, 3)], normal_hint=rotation[:, 2], mesh_origin=anchor
        )
        self.assertEqual(result.spec.location, tuple(anchor))
        self.assertLess(np.max(np.abs(result.spec.vertices)), 20)
        xyz = np.asarray(result.spec.vertices) @ rotation
        validate_mesh(
            replace(result.roof.mesh, vertices=tuple(map(tuple, xyz))),
            Polygon(p[:, :2]),
            tolerance=1e-5,
        )
        self.assertGreater(result.roof.validation.features.get("ridge", 0), 0)
        for part in result.roof.topology.parts:
            self.assertTrue(part.plane_definitions)
        self.assertTrue(result.roof.topology.features)
        # Roof semantics are present on topology before the tessellation layer.
        self.assertEqual({f.kind for f in result.roof.topology.features}, {"ridge"})

    def test_validator_detects_corrupt_meshes(self):
        result = generate_roof(
            [(0, 0), (12, 0), (12, 6), (0, 6)], RoofParameters("hip")
        )
        mesh = result.normalized_mesh
        corrupt = [
            replace(mesh, faces=mesh.faces + (mesh.faces[0],)),
            replace(mesh, faces=mesh.faces[:-1]),
            replace(mesh, faces=((0, 1, 999),) + mesh.faces[1:]),
            replace(mesh, faces=(tuple(reversed(mesh.faces[0])),) + mesh.faces[1:]),
            replace(mesh, vertices=mesh.vertices + (mesh.vertices[0],)),
        ]
        vertices = list(mesh.vertices)
        p = list(vertices[2])
        p[2] += 0.02
        vertices[2] = tuple(p)
        corrupt.append(replace(mesh, vertices=tuple(vertices)))
        for item in corrupt:
            with (
                self.subTest(faces=item.faces),
                self.assertRaises(UnsupportedRoofError),
            ):
                validate_mesh(item, result.footprint.polygon, tolerance=EPS * 20)


if __name__ == "__main__":
    unittest.main()
