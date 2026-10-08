# SPDX-License-Identifier: GPL-3.0-or-later
"""Nonexclusive rejection counts, censoring and streaming-memory contract."""

from pathlib import Path
import sys
import unittest
import python

# Developer scripts share this directory's imports; the runtime never imports it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_roof_support import summarize


def row(status, assignments, elapsed=2):
    return {
        "status": status,
        "rejected": [
            {
                "reason": "authored diagnostic",
                "issues": [
                    {"stage": "relation", "code": code, "cells": [0, 1]}
                    for code in codes
                ],
            }
            for codes in assignments
        ],
        "continuation_geometry": {},
        "timings_ms": {"total": elapsed},
    }


class SupportAuditProof(unittest.TestCase):
    def test_all_assignment_causes_are_nonexclusive_and_stream_once(self):
        rows = [
            (
                row(
                    "unsupported",
                    [["parallel", "parallel", "partial_end"], ["parallel"]],
                ),
                1,
            ),
            (row("supported", [["partial_end"]]), 2),
            (row("incomplete", [["continuation"]]), 1),
        ]
        expected = summarize(rows)
        self.assertEqual(expected, summarize(iter(rows)))
        self.assertEqual(
            expected["building_status"],
            {"supported": 2, "unsupported": 1, "incomplete": 1},
        )
        self.assertEqual(
            expected["building_incidence_nonexclusive"],
            {
                "relation.partial_end": 3,
                "relation.parallel": 1,
                "relation.continuation": 1,
            },
        )
        self.assertEqual(
            expected["rejected_assignment_incidence_nonexclusive"],
            {
                "relation.partial_end": 3,
                "relation.parallel": 2,
                "relation.continuation": 1,
            },
        )
        self.assertEqual(expected["issue_occurrences"]["relation.parallel"], 3)
        self.assertEqual(
            expected["conditional_sole_known_blocker_buildings"],
            {"relation.parallel": 1},
        )
        self.assertEqual(expected["total_ms"], 8)


if __name__ == "__main__":
    unittest.main()
