# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent constrained least-squares, coupled ridge and solver-class proofs."""

import python
from dataclasses import replace
import unittest
from unittest.mock import patch
import numpy as np
from roof_generator.core.solve import GeometryProblem, embed
from roof_generator.core.plane_embedding import embed_planes
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.core.generation import prepare_generation
from python.inspect_architectural_parts import fixture


def independent_solution(problem):
    coordinates = [(i, k) for i in problem.variable_xy for k in (0, 1)] + [
        (i, 2) for i in problem.variable_z
    ]
    ids = {c: j for j, c in enumerate(coordinates)}
    points = np.array(problem.initial_vertices)
    for i, z in problem.fixed_z:
        points[i, 2] = z
    rows, rhs = [], []

    def add(coefficients, value):
        row = np.zeros(len(coordinates))
        for coordinate, coefficient in coefficients.items():
            if coordinate in ids:
                row[ids[coordinate]] += coefficient
            else:
                value -= coefficient * points[coordinate]
        rows.append(row)
        rhs.append(value)

    for face, origin, direction, pitch in problem.slope_constraints:
        for i in problem.faces[face]:
            add({(i, 0): -pitch * direction[0], (i, 1): -pitch * direction[1], (i, 2): 1},
                origin[2] - pitch * np.dot(origin[:2], direction))
    for (a, b), (dx, dy) in problem.ridge_directions:
        add({(a, 0): -dy, (b, 0): dy, (a, 1): dx, (b, 1): -dx}, 0)
    matrix = np.array(rows)
    values = np.linalg.lstsq(matrix, rhs, rcond=1e-12)[0]
    _, singular, right = np.linalg.svd(matrix, full_matrices=True)
    rank = np.count_nonzero(singular > 1e-12)
    null = right[rank:].T
    xy = [j for j, (_, k) in enumerate(coordinates) if k < 2]
    if null.shape[1]:
        target = np.array([points[coordinates[j]] for j in xy]) - values[xy]
        values += null @ np.linalg.lstsq(null[xy], target, rcond=1e-12)[0]
    for coordinate, value in zip(coordinates, values):
        points[coordinate] = value
    return points


def sliding_problem():
    return GeometryProblem(
        ((0., 0., 0.), (2., 0., 1.), (2., 3., 9.), (0., 1., -8.)),
        ((0, 1, 2, 3),), (2, 3), (2, 3), ((0, 0.), (1, 1.)),
        (((2, 3), (1., 0.)),), ((0, (0., 0., 0.), (1., 0.), .5),),
    )


class PlaneEmbeddingTests(unittest.TestCase):
    def test_rank_deficient_planes_use_joint_ridge_and_nearest_xy(self):
        p = sliding_problem()
        actual = embed_planes(p)
        np.testing.assert_allclose(actual, ((0, 0, 0), (2, 0, 1), (2, 2, 1), (0, 2, 0)), atol=1e-14)
        np.testing.assert_allclose(actual, independent_solution(p), atol=1e-13)
        self.assertEqual(embed_planes(p), actual)

    def test_incident_plane_intersection_agrees_with_svd_oracle(self):
        for name in ('orthogonal_L', 'orthogonal_U', 'cross', 'residential_multi_reflex', 'grid_20'):
            with self.subTest(name=name):
                generation = prepare_generation(fixture(name)['footprint'])
                for candidate in generation.candidates.valid:
                    p = candidate.geometry
                    actual = embed_planes(p)
                    np.testing.assert_allclose(actual, independent_solution(p), atol=1e-10)
                    np.testing.assert_allclose(actual, candidate.mesh.vertices, atol=1e-10)
                    self.assertEqual(p.faces, tuple(f.loop for f in candidate.graph.faces))

    def test_conflicting_anchor_and_fixed_ridge_fail(self):
        p = sliding_problem()
        with self.assertRaises(UnsupportedRoofError):
            embed_planes(replace(p, variable_z=(3,), fixed_z=((0, 0.), (1, 1.), (2, 8.)),
                                 variable_xy=(3,)))
        with self.assertRaises(UnsupportedRoofError):
            embed_planes(replace(p, variable_xy=()))

    def test_incomplete_plane_contract_is_not_a_direct_solve(self):
        p = replace(sliding_problem(), slope_constraints=())
        with self.assertRaisesRegex(UnsupportedRoofError, 'plane for every face'):
            embed_planes(p)

    def test_dispatch_uses_constraints_and_never_retries_failure(self):
        generation = prepare_generation(fixture('orthogonal_L')['footprint'])
        graph, p = generation.selected.graph, generation.geometry_problem
        with patch('roof_generator.core.optimization.optimize', side_effect=AssertionError('nonlinear retry')):
            self.assertEqual(embed(graph, p), embed_planes(p))
            fixed = dict(p.fixed_z)
            index = next(iter(fixed))
            fixed[index] += 1
            with self.assertRaises(UnsupportedRoofError):
                embed(graph, replace(p, fixed_z=tuple(fixed.items())))
        with patch('roof_generator.core.optimization.optimize', side_effect=UnsupportedRoofError('generic solve')) as generic:
            with self.assertRaisesRegex(UnsupportedRoofError, 'generic solve'):
                embed(graph, replace(p, slope_constraints=()))
            self.assertEqual(generic.call_count, 1)
