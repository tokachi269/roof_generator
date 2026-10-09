# SPDX-License-Identifier: GPL-3.0-or-later
"""Observed alternative failure sets must not become assignment incidence."""
import unittest
from python.causal_roof_audit import minimal_sets


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


if __name__ == '__main__':unittest.main()
