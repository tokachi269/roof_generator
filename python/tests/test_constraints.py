# SPDX-License-Identifier: GPL-3.0-or-later
"""Linear plane inconsistency is necessary embedding evidence, not topology."""
import unittest
from dataclasses import replace
import python
from roof_generator.core.solve import GeometryProblem
from roof_generator.core.constraints import check_planes
from roof_generator.core.errors import UnsupportedRoofError


class PlaneFeasibility(unittest.TestCase):
    def test_parallel_incompatible_declared_planes_reject_without_mutating_problem(self):
        problem=GeometryProblem(((0.,0.,0.),(1.,0.,0.),(0.,1.,0.),(1.,1.,0.),(0.,2.,0.)),
            ((0,1,2),(0,3,4)),tuple(range(5)),tuple(range(5)),(),(),
            ((0,(0.,0.,0.),(1.,0.),1.),(1,(0.,0.,1.),(1.,0.),1.)))
        snapshot=replace(problem)
        with self.assertRaisesRegex(UnsupportedRoofError,'inconsistent'):check_planes(problem)
        self.assertEqual(problem,snapshot)
        compatible=replace(problem,slope_constraints=((0,(0.,0.,0.),(1.,0.),1.),
                                                     (1,(0.,0.,0.),(1.,0.),1.)))
        check_planes(compatible)
        self.assertEqual(compatible.initial_vertices,problem.initial_vertices)


if __name__=='__main__':unittest.main()
