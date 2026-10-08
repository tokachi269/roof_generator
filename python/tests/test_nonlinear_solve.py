# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent covariance, planar witness and projection proofs."""

import python
from dataclasses import replace
import math
import unittest
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from roof_generator.core.generation import (
    generate_roof,
    prepare_generation,
    GenerationSettings,
)
from roof_generator.core.optimization import covariance_plane, optimize
from roof_generator.core.mesh import RoofMesh
from roof_generator.core.errors import UnsupportedRoofError
from python.inspect_architectural_parts import fixture


class NonlinearSolveTests(unittest.TestCase):
    def test_residual_norm_is_published_covariance_eigenvalue(self):
        rng = np.random.default_rng(1281)
        for _ in range(30):
            points = rng.normal(size=(9, 3))
            normal, residual = covariance_plane(points)
            expected = np.linalg.eigvalsh(np.cov(points, rowvar=False))[0]
            self.assertAlmostEqual(
                sum(x * x for x in residual) / 8, expected, places=12
            )
            self.assertAlmostEqual(sum(x * x for x in normal), 1, places=12)

    def check(self, raw, settings=GenerationSettings()):
        result = generate_roof(raw, settings)
        p = result.generation.geometry_problem
        mesh = result.mesh
        self.assertIs(mesh.graph, result.generation.selected.graph)
        self.assertEqual(mesh.faces, p.faces)
        xyz = np.asarray(mesh.vertices)
        for i, z in p.fixed_z:
            self.assertEqual(xyz[i, 2], z)
        for i in set(range(len(xyz))) - set(p.variable_xy):
            np.testing.assert_array_equal(xyz[i, :2], p.initial_vertices[i][:2])
        for (a, b), direction in p.ridge_directions:
            self.assertLess(
                abs(
                    (xyz[b, 0] - xyz[a, 0]) * direction[1]
                    - (xyz[b, 1] - xyz[a, 1]) * direction[0]
                ),
                1e-10,
            )
        polys = []
        for f in mesh.faces:
            points = xyz[list(f)]
            self.assertLess(
                np.linalg.svd(points - points.mean(axis=0), compute_uv=False)[-1], 4e-8
            )
            poly = Polygon(points[:, :2])
            self.assertTrue(poly.is_valid and poly.area > 0)
            polys.append(poly)
        outline = Polygon(mesh.graph.outline)
        self.assertLess(unary_union(polys).symmetric_difference(outline).area, 1e-10)
        self.assertLess(abs(sum(p.area for p in polys) - outline.area), 1e-10)
        self.assertEqual(generate_roof(raw, settings), result)
        return result

    def test_compound_existing_graphs_solve_without_topology_edits(self):
        for name in ("orthogonal_L", "orthogonal_T", "orthogonal_U", "cross"):
            with self.subTest(name=name):
                self.check(fixture(name)["footprint"])

    def test_reported_energy_excludes_pitch_and_regularization(self):
        generation = prepare_generation(fixture("orthogonal_U")["footprint"])
        embedding = optimize(generation.geometry_problem)
        points = np.asarray(embedding.vertices)
        expected = sum(
            np.linalg.eigvalsh(np.cov(points[list(face)], rowvar=False))[0]
            for face in generation.geometry_problem.faces
        )
        self.assertAlmostEqual(embedding.energy, expected, places=14)

    def test_independent_terminal_witness_matches_solved_heights_and_positions(self):
        from python.tests.test_terminal_network import witness

        # Authored eave planes, not production geometry helpers.
        for widths in ((6, 4, 4), (4, 6, 6), (6, 4, 8)):
            raw, points, faces = witness(*widths)
            result = self.check(raw, GenerationSettings(seed=13))
            actual = [
                result.generation.footprint.frame.world_xyz(p)
                for p in result.mesh.vertices
            ]
            self.assertEqual(len(actual), len(points))
            for expected in points.values():
                self.assertLess(min(math.dist(expected, p) for p in actual), 1e-5)

    def test_transforms_do_not_change_physical_embedding(self):
        raw = np.asarray(fixture("orthogonal_U")["footprint"])
        r = self.check(raw)
        angle = 0.613
        rotation = np.array(
            [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
        )
        expected = np.asarray(
            [r.generation.footprint.frame.world_xyz(p) for p in r.mesh.vertices]
        )
        for variant in (
            raw[::-1],
            np.roll(raw, 3, axis=0),
            np.array(
                [
                    p
                    for a, b in zip(raw, np.roll(raw, -1, axis=0))
                    for p in (a, (a + b) / 2)
                ]
            ),
        ):
            moved = self.check(
                variant @ rotation.T + [37, -13],
                GenerationSettings(reference_direction=tuple(rotation @ [1, 0])),
            )
            xyz = np.asarray(
                [
                    moved.generation.footprint.frame.world_xyz(p)
                    for p in moved.mesh.vertices
                ]
            )
            actual = sorted(
                tuple(np.round((*((p[:2] - [37, -13]) @ rotation), p[2]), 6))
                for p in xyz
            )
            self.assertEqual(actual, sorted(tuple(np.round(p, 6)) for p in expected))

    def test_iteration_failure_is_explicit_and_does_not_return_approximate_mesh(self):
        g = prepare_generation(fixture("orthogonal_U")["footprint"])
        with self.assertRaisesRegex(UnsupportedRoofError, "did not converge"):
            optimize(g.geometry_problem, max_iterations=1)
        with self.assertRaises(UnsupportedRoofError):
            replace(
                g.geometry_problem,
                variable_z=tuple(range(len(g.geometry_problem.initial_vertices))),
            )
