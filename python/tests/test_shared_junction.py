# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent equal-width four-port witness, not generated plane topology."""

from collections import Counter
import python
import unittest
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose
from python.tests.architecture_setup import compose
from roof_generator.core.mesh import RoofMesh
from roof_generator.core.solve import problem
from roof_generator.core.initialization import _valid_drawing


class SharedJunctionProof(unittest.TestCase):
    def test_opposite_equal_ports_have_one_degree_eight_junction_and_planar_witness(
        self,
    ):
        raw = (
            (0, 0),
            (6, 0),
            (6, -6),
            (10, -6),
            (10, 0),
            (16, 0),
            (16, 4),
            (10, 4),
            (10, 10),
            (6, 10),
            (6, 4),
            (0, 4),
        )
        fp = analyze(raw)
        result = compose(decompose(fp))
        graph = result.graph
        internal = [i for i, v in enumerate(graph.vertices) if v.boundary is None]
        self.assertEqual(len(internal), 1)
        joint = internal[0]
        self.assertEqual(
            Counter(e.kind for e in graph.edges if joint in e.vertices),
            {"ridge": 4, "valley": 4},
        )
        self.assertEqual(len(graph.faces), 8)
        # Independent known uniform-width cross: z=1 at ridge caps/center,
        # z=0 at all physical corners. Equal pitch is 0.5 over width 4.
        xyz = []
        for i, v in enumerate(graph.vertices):
            xy = fp.frame.world_xy(v.seed) if i != joint else (8, 2)
            z = 1 if v.role != "corner" else 0
            ux, uy = fp.frame.direction
            dx, dy = (xy[k] - fp.frame.origin[k] for k in (0, 1))
            xyz.append(
                (
                    (dx * ux + dy * uy) / fp.frame.scale,
                    (-dx * uy + dy * ux) / fp.frame.scale,
                    z / fp.frame.scale,
                )
            )
        RoofMesh(graph, tuple(xyz))
        self.assertEqual(problem(graph).faces, tuple(f.loop for f in graph.faces))
        self.assertEqual({c.junctions for c in result.connections}, {(joint,)})


if __name__ == "__main__":
    unittest.main()
