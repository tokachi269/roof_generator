# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from dataclasses import replace
from python.graph_first.footprint import analyze
from python.graph_first.cells import decompose
from python.graph_first.parts import ArchitecturalPartGraph, Member, Part
from python.graph_first.graph import UnsupportedGraphError


class PartContractProof(unittest.TestCase):
    def rectangle(self):
        d = decompose(analyze(((0, 0), (12, 0), (12, 5), (0, 5))))
        c = d.cells[0]
        p = Part(
            0,
            (0,),
            (c.boundary,),
            tuple(s for side in c.sides for s in side.exterior),
            (),
            (0,),
        )
        bounds = tuple(v for k in (0, 1) for v in ())
        m = Member(0, (0, 0, 1, 1), (0,))
        return ArchitecturalPartGraph(d, (m,), (p,), (), (), ())

    def test_contract_is_not_roofgraph(self):
        g = self.rectangle()
        self.assertIsNone(g.inspect()["roof_topology"])
        self.assertEqual(g.parts[0].cells, (0,))
        self.assertFalse(hasattr(g, "faces"))

    def test_missing_membership_boundary_or_provenance_is_rejected(self):
        g = self.rectangle()
        for bad in (
            replace(g.parts[0], cells=()),
            replace(g.parts[0], boundaries=()),
            replace(g.parts[0], exterior=()),
            replace(g.parts[0], consumed=((0, 1),)),
        ):
            with self.assertRaises(UnsupportedGraphError):
                replace(g, parts=(bad,))


if __name__ == "__main__":
    unittest.main()
