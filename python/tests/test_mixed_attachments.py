# SPDX-License-Identifier: GPL-3.0-or-later
"""Literal incidence and equal-pitch witness for separated end/side ports."""

import python
from collections import Counter
from dataclasses import replace
import math
import unittest
import numpy as np
from roof_generator.core.generation import (
    generate_roof,
    prepare_generation,
    GenerationSettings,
)
from python.tests.architecture_setup import compose
from roof_generator.core.errors import UnsupportedRoofError


def network(width=6, arm=4, start=16, end=20, length=32):
    return (
        (0, 0),
        (length, 0),
        (length, width),
        (end, width),
        (end, 14),
        (start, 14),
        (start, width),
        (arm, width),
        (arm, 14),
        (0, 14),
    )


class MixedAttachmentProof(unittest.TestCase):
    def test_literal_witness_and_incidence_consume_all_caps_and_cuts(self):
        r = generate_roof(network())
        g = r.mesh.graph
        expected = (
            (0, 0, 0),
            (32, 0, 0),
            (32, 6, 0),
            (20, 6, 0),
            (20, 14, 0),
            (16, 14, 0),
            (16, 6, 0),
            (4, 6, 0),
            (4, 14, 0),
            (0, 14, 0),
            (32, 3, 1.5),
            (18, 14, 1),
            (2, 14, 1),
            (3, 3, 1.5),
            (2, 4, 1),
            (18, 4, 1),
        )
        actual = [r.generation.footprint.frame.world_xyz(p) for p in r.mesh.vertices]
        self.assertEqual(len(actual), len(expected))
        for p in expected:
            self.assertLess(min(math.dist(p, q) for q in actual), 1e-6)
        self.assertEqual(len(g.faces), 6)
        self.assertEqual(
            Counter(e.kind for e in g.edges if len(e.faces) == 2),
            {"ridge": 3, "valley": 3, "hip": 2},
        )
        self.assertEqual(
            {c.kind for c in r.generation.selected.composition.connections},
            {"terminal", "middle"},
        )
        self.assertEqual(len(g.vertices) - len(g.edges) + len(g.faces), 1)
        d = r.generation.selected.architecture.decomposition
        self.assertEqual(
            compose(
                replace(d, adjacency=d.adjacency[::-1]), axes=r.generation.selected.axes
            ).graph,
            g,
        )
        self.assertEqual({c for f in g.faces for c in f.cells}, {0, 1, 2})
        self.assertEqual(
            {i for e in g.edges if e.boundary for i in e.boundary.original_edges},
            set(range(10)),
        )

    def test_parameterized_networks_and_rigid_metamorphisms(self):
        for width, arm in ((6, 4), (7, 5), (5, 3.5), (6, 8)):
            raw = np.array(network(width, arm, start=18, end=21, length=36))
            base = generate_roof(raw)
            angle = 0.357
            rot = np.array(
                [
                    [math.cos(angle), -math.sin(angle)],
                    [math.sin(angle), math.cos(angle)],
                ]
            )
            moved = generate_roof(
                np.roll(raw[::-1], 4, axis=0) @ rot.T + [71, -33],
                GenerationSettings(reference_direction=tuple(rot @ [1, 0])),
            )
            expected = sorted(
                tuple(np.round(base.generation.footprint.frame.world_xyz(p), 6))
                for p in base.mesh.vertices
            )
            actual = [
                moved.generation.footprint.frame.world_xyz(p)
                for p in moved.mesh.vertices
            ]
            actual = sorted(
                tuple(np.round((*((np.array(p[:2]) - [71, -33]) @ rot), p[2]), 6))
                for p in actual
            )
            self.assertEqual(actual, expected)

    def test_two_consumed_receiver_ends_with_multiple_middle_ports(self):
        from python.branch_network_corpus import corpus

        raw = corpus()["corpora"]["structured_branch_network"][1]["footprint"]
        r = generate_roof(raw)
        self.assertEqual(len(r.mesh.faces), 10)
        self.assertEqual(
            Counter(e.kind for e in r.mesh.graph.edges if len(e.faces) == 2),
            {"ridge": 5, "valley": 6, "hip": 4},
        )
        self.assertEqual(
            Counter(c.kind for c in r.generation.selected.composition.connections),
            {"terminal": 2, "middle": 2},
        )

    def test_near_end_and_equal_width_middle_are_not_silently_spliced(self):
        # Some alternate partitions can have another justified interpretation;
        # inspect the explicit mixed operation, rather than assuming a shape
        # can never be roofed.
        from roof_generator.core.member_layout import minimum_layout
        from roof_generator.core.junctions import _mixed_plan
        from python.tests.architecture_setup import fixed_port_fixture as attachments
        from roof_generator.core.topology import cell_primitives
        from roof_generator.core.partition_candidates import candidates
        from roof_generator.core.footprint import analyze

        for raw in (network(start=5, end=8), network(start=14, end=20)):
            found = 0
            for d in candidates(analyze(raw)).candidates:
                p = cell_primitives(d)
                relations = attachments(d, p)
                if {r.kind for r in relations} == {"terminal", "middle"}:
                    found += 1
                    with self.assertRaises(UnsupportedRoofError):
                        _mixed_plan(minimum_layout(d), p, relations)
            self.assertGreater(found, 0)
