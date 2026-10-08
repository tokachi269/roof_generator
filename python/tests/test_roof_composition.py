# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent published-attachment fixtures and pre-edit relation proofs."""

from collections import Counter
from pathlib import Path
import json
import unittest

from python.graph_first.footprint import analyze
from python.graph_first.cells import decompose
from python.graph_first.topology import _rectangle_graph
from python.graph_first.connections import plan
from python.graph_first.graph import UnsupportedGraphError

RECORDS = json.loads(
    (Path(__file__).parent / "fixtures/rectangle_partition.json").read_text()
)


def primitives(d):
    return tuple(
        _rectangle_graph(
            tuple(d.vertices[i] for i in c.corners),
            tuple(
                tuple(
                    sorted({i for span in side.exterior for i in span.original_edges})
                )
                for side in c.sides
            ),
            "gable",
            cell=c.id,
        )
        for c in d.cells
    )


class AttachmentRelationTests(unittest.TestCase):
    def test_terminal_and_middle_ports_are_selected_before_graph_edits(self):
        for name, kind in (("orthogonal_L", "terminal"), ("orthogonal_T", "middle")):
            with self.subTest(name=name):
                record = next(r for r in RECORDS if r["name"] == name)
                d = decompose(analyze(record["footprint"]))
                p = primitives(d)
                before = tuple(g.inspect() for g in p)
                (r,) = plan(d, p)
                self.assertEqual(r.kind, kind)
                self.assertIsNotNone(r.branch_port)
                self.assertEqual(r.host_port is None, kind == "middle")
                self.assertEqual(before, tuple(g.inspect() for g in p))
                self.assertEqual(set(r.shared), set(d.adjacency[0].interval))
                self.assertEqual(
                    p[r.branch].vertices[r.branch_port].boundary.edge, r.branch_side
                )

    def test_unrecognized_arrangements_are_not_completed_by_independent_gables(self):
        for name in ("orthogonal_U", "cross", "residential_multi_reflex"):
            record = next(r for r in RECORDS if r["name"] == name)
            d = decompose(analyze(record["footprint"]))
            with self.subTest(name=name), self.assertRaises(UnsupportedGraphError):
                plan(d, primitives(d))


if __name__ == "__main__":
    unittest.main()
