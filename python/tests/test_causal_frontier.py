# SPDX-License-Identifier: GPL-3.0-or-later
"""Observed alternative failure sets must not become assignment incidence."""
import unittest
from python.causal_roof_audit import minimal_sets, source_frontier


class CausalFrontierProof(unittest.TestCase):
    def test_smaller_failure_alternative_dominates_only_its_supersets(self):
        candidates = [{'parallel'}, {'parallel','partial_end'},
                      {'offset_continuation'}, {'parallel'}]
        self.assertEqual(minimal_sets(candidates),
                         [['offset_continuation'], ['parallel']])

    def test_incomparable_joint_requirements_are_retained(self):
        candidates = [{'parallel','partial_end'}, {'parallel','offset_continuation'}]
        self.assertEqual(minimal_sets(candidates),
                         [['offset_continuation','parallel'], ['parallel','partial_end']])
        self.assertEqual(minimal_sets(reversed(candidates)),minimal_sets(candidates))

    def test_failed_parallel_alternative_does_not_hide_success(self):
        result=source_frontier([(True,'relation'),(False,'mesh')],True)
        self.assertEqual(result['state'],'parallel_free_candidate')
        self.assertEqual(result['parallel_free_mesh_assignments'],1)
        self.assertEqual(result['parallel_free_max_reached_stage'],'mesh')

    def test_empty_model_family_does_not_establish_parallel_unavoidability(self):
        result=source_frontier([],True,model_failures=3)
        self.assertEqual(result['state'],'no_modeled_candidate')
        self.assertIsNone(result['parallel_free_max_reached_stage'])

    def test_unfinished_family_cannot_establish_parallel_unavoidability(self):
        result=source_frontier([(True,'relation')],False)
        self.assertEqual(result['state'],'incomplete')


if __name__ == '__main__':unittest.main()
