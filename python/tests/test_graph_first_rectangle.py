# SPDX-License-Identifier: GPL-3.0-or-later
"""Analytic primitive proofs, graph metamorphisms and secondary differential."""

from collections import Counter
from dataclasses import replace
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace

import numpy as np
from python.graph_first.footprint import analyze
from python.graph_first.topology import rectangle_graph
from python.graph_first.geometry import solve_rectangle, problem
from python.graph_first.graph import UnsupportedGraphError
from python.tests.graph_first_reference import rectangle_snapshot
from python.roof_harness import capture, differences
from python.tests.test_roof_harness import assert_rectangle, assert_disk

ROOT = Path(__file__).resolve().parents[2]


def graph_signature(footprint, graph, rotation=np.eye(2), translation=np.zeros(2)):
    """Inspect output only; independent rigid-transform equivalence oracle."""
    points = (
        np.asarray([footprint.frame.world_xy(v.seed) for v in graph.vertices])
        - translation
    ) @ rotation
    keys = [(v.role, tuple(np.round(p, 6))) for p, v in zip(points, graph.vertices)]
    edge_keys = sorted(
        (tuple(sorted((keys[e.vertices[0]], keys[e.vertices[1]]))), e.kind)
        for e in graph.edges
    )
    faces = []
    outline = (
        np.asarray([footprint.frame.world_xy(p) for p in graph.outline]) - translation
    ) @ rotation
    for f in graph.faces:
        ring = tuple(keys[i] for i in f.loop)
        eaves = tuple(
            sorted(
                tuple(
                    sorted(
                        (
                            tuple(np.round(outline[e], 6)),
                            tuple(np.round(outline[(e + 1) % len(outline)], 6)),
                        )
                    )
                )
                for e in f.eaves
            )
        )
        faces.append(
            (min(ring[i:] + ring[:i] for i in range(len(ring))), f.cells, eaves)
        )
    return sorted(keys), edge_keys, sorted(faces)


class RectangleGraphTests(unittest.TestCase):
    def test_four_primitive_graphs_and_analytic_mesh_primary(self):
        fp = analyze([(0, 0), (12, 0), (12, 6), (0, 6)])
        expected = {
            "gable": (6, 2, {"ridge": 1, "eave": 2, "gable_end": 4}),
            "hip": (6, 4, {"ridge": 1, "hip": 4, "eave": 4}),
            "flat": (4, 1, {"eave": 4}),
            "shed": (4, 1, {"eave": 2, "gable_end": 2}),
        }
        for kind, (vertices, faces, labels) in expected.items():
            with self.subTest(kind=kind):
                graph = rectangle_graph(fp, kind)
                mesh = solve_rectangle(graph, eave_height=2 / fp.frame.scale)
                self.assertEqual(
                    (len(graph.vertices), len(graph.faces)), (vertices, faces)
                )
                self.assertEqual(Counter(e.kind for e in graph.edges), labels)
                self.assertEqual(
                    set(e.boundary.edge for e in graph.edges if e.boundary is not None),
                    set(range(4)),
                )
                world = SimpleNamespace(
                    vertices=tuple(fp.frame.world_xyz(p) for p in mesh.vertices),
                    faces=mesh.faces,
                    edge_features=mesh.edge_features,
                )
                assert_disk(self, world)
                if kind in {"gable", "hip"}:
                    assert_rectangle(self, SimpleNamespace(mesh=world), kind)
                else:
                    for x, y, z in world.vertices:
                        self.assertAlmostEqual(
                            z, 2 if kind == "flat" else 2 + 0.5 * y, places=7
                        )
                self.assertEqual(mesh.faces, tuple(f.loop for f in graph.faces))
                self.assertIs(mesh.graph, graph)

    def test_solver_problem_has_fixed_incidence_and_explicit_nonflat_anchors(self):
        fp = analyze([(0, 0), (13.6, 0), (13.6, 8.4), (0, 8.4)])
        g = rectangle_graph(fp, "hip")
        before = g.inspect()
        p = problem(g, pitch=0.4)
        q = problem(g, pitch=0.8)
        self.assertEqual(p.faces, q.faces)
        self.assertEqual(p.variable_xy, (4, 5))
        self.assertEqual(p.variable_z, ())
        self.assertGreater(p.fixed_z[-1][1], 0)
        self.assertEqual(g.inspect(), before)
        # Harmonic seeds are disposable; the exact hip solve moves them.
        m = solve_rectangle(g)
        self.assertNotEqual(
            tuple(v.seed for v in g.vertices), tuple(v[:2] for v in m.vertices)
        )
        self.assertTrue(all(not hasattr(f, "plane") for f in g.faces))

    def test_rectangle_secondary_semantic_harness_unchanged(self):
        fixtures = json.loads(
            (ROOT / "python/tests/fixtures/roof_acceptance.json").read_text()
        )
        cases = [
            c
            for c in fixtures
            if c["name"]
            in (
                "rectangle_gable",
                "rectangle_hip",
                "rectangle_shed",
                "rotated_rectangle",
            )
        ]
        cases.append(dict(cases[0], name="rectangle_flat", roof_type="flat"))
        for c in cases:
            with self.subTest(case=c["name"]):
                f = analyze(c["footprint"])
                g = rectangle_graph(f, c["roof_type"])
                m = solve_rectangle(g, c["pitch"])
                self.assertEqual(differences(capture(c), rectangle_snapshot(f, m)), [])

    def test_rectangle_graph_metamorphisms_and_redundant_provenance(self):
        original = np.array([(0, 0), (12, 0), (12, 6), (0, 6)], float)
        angle = 0.713
        r = np.array(
            [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
        )
        variants = [
            (original, np.eye(2), np.zeros(2)),
            (np.roll(original, 2, axis=0), np.eye(2), np.zeros(2)),
            (original[::-1], np.eye(2), np.zeros(2)),
            (original @ r.T + [281, -73], r, np.array([281, -73])),
        ]
        subdivided = []
        for a, b in zip(original, np.roll(original, -1, axis=0)):
            subdivided.extend((a, (a + b) / 2))
        variants.append((subdivided, np.eye(2), np.zeros(2)))

        def graph_with_intent(fp, kind, rotation=np.eye(2), translation=np.zeros(2)):
            # A rectangle has no inherent directed low eave. Supply the same
            # physical shed direction rather than inventing it from winding.
            low = None
            if kind == "shed":
                p = (
                    np.asarray([fp.frame.world_xy(v) for v in fp.vertices])
                    - translation
                ) @ rotation
                low = next(
                    i
                    for i in range(4)
                    if abs(p[i][1]) < 1e-7 and abs(p[(i + 1) % 4][1]) < 1e-7
                )
            return rectangle_graph(fp, kind, shed_edge=low)

        for kind in ("gable", "hip", "shed", "flat"):
            f = analyze(original)
            reference = graph_signature(f, graph_with_intent(f, kind))
            for points, rotation, translation in variants:
                fp = analyze(points)
                g = graph_with_intent(fp, kind, rotation, translation)
                self.assertEqual(
                    graph_signature(fp, g, rotation, translation), reference
                )
                self.assertEqual(
                    {i for ids in fp.source_edges for i in ids}, set(range(len(points)))
                )

    def test_no_legacy_or_polygon_runtime_dependency_in_fresh_process(self):
        script = """import sys,builtins
sys.path.insert(0,sys.argv[1])
original=builtins.__import__
def checked(name,*args,**kwargs):
 if name=="shapely" or name.startswith(("shapely.","roof_generator")):raise AssertionError("forbidden new-path import: "+name)
 return original(name,*args,**kwargs)
builtins.__import__=checked
from python.graph_first.footprint import analyze
from python.graph_first.topology import rectangle_graph
from python.graph_first.geometry import solve_rectangle
for kind in ("gable","hip","shed","flat"):
 g=rectangle_graph(analyze(((0,0),(12,0),(12,6),(0,6))),kind)
 assert solve_rectangle(g).faces
"""
        result = subprocess.run(
            [sys.executable, "-I", "-c", script, str(ROOT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unsupported_and_square_hip(self):
        with self.assertRaises(UnsupportedGraphError):
            analyze([(0, 0), (1, 1), (0, 1), (1, 0)])
        with self.assertRaises(UnsupportedGraphError):
            rectangle_graph(analyze([(0, 0), (12, 0), (11, 6), (0, 6)]))
        g = rectangle_graph(analyze([(0, 0), (6, 0), (6, 6), (0, 6)]), "hip")
        self.assertEqual(len(g.vertices), 5)
        self.assertEqual(len(g.faces), 4)
        self.assertEqual(Counter(e.kind for e in g.edges), {"hip": 4, "eave": 4})


if __name__ == "__main__":
    unittest.main()
