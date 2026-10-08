# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent published-attachment fixtures and pre-edit relation proofs."""

from collections import Counter
from pathlib import Path
import json
import unittest

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from python.graph_first.footprint import analyze
from python.graph_first.cells import decompose
from python.graph_first.topology import _rectangle_graph
from python.graph_first.connections import plan
from python.graph_first.graph import UnsupportedGraphError

RECORDS = json.loads(
    (Path(__file__).parent / "fixtures/rectangle_partition.json").read_text()
)
REFERENCES = json.loads(
    (Path(__file__).parent / "fixtures/roof_composition.json").read_text()
)


class PublishedFixtureTests(unittest.TestCase):
    def test_independently_authored_cycles_have_a_planar_nonzero_embedding(self):
        for record in REFERENCES:
            with self.subTest(name=record["name"]):
                points, faces = record["points"], record["faces"]
                counts = Counter(
                    tuple(sorted((a, b)))
                    for f in faces
                    for a, b in zip(f, f[1:] + f[:1])
                )
                degree = Counter(v for edge in counts for v in edge)
                self.assertEqual(
                    sorted(degree[v] for v in record["junctions"]),
                    record["junction_degrees"],
                )
                self.assertEqual(len(points) - len(counts) + len(faces), 1)
                self.assertEqual(set(counts.values()), {1, 2})
                roof_edges = {
                    tuple(sorted(edge))
                    for kind in ("ridge", "valley", "hip")
                    for edge in record[kind]
                }
                self.assertEqual(
                    roof_edges, {edge for edge, count in counts.items() if count == 2}
                )
                polygons = []
                for face in faces:
                    xyz = np.array([points[i] for i in face], dtype=float)
                    self.assertLess(
                        np.linalg.svd(xyz - xyz.mean(axis=0), compute_uv=False)[-1],
                        1e-9,
                    )
                    self.assertGreater(np.ptp(xyz[:, 2]), 0)
                    polygons.append(Polygon(xyz[:, :2]))
                shape = Polygon([points[i][:2] for i in record["outline"]])
                self.assertTrue(all(p.is_valid and p.area > 0 for p in polygons))
                self.assertLess(
                    unary_union(polygons).symmetric_difference(shape).area, 1e-9
                )
                self.assertLess(abs(sum(p.area for p in polygons) - shape.area), 1e-9)
                d = decompose(analyze([points[i][:2] for i in record["outline"]]))
                self.assertEqual(len(d.cells), record["cells"])


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
