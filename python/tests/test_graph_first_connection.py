# SPDX-License-Identifier: GPL-3.0-or-later
"""Pre-solver terminal-graft proof; independent witness and secondary reference."""

from collections import Counter
from dataclasses import replace
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import python
import unittest

import numpy as np
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose, Cell, Side, Adjacency, Decomposition
from roof_generator.core.topology import compose
from roof_generator.core.solve import problem, solve_rectangle
from roof_generator.core.mesh import RoofMesh
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.core.provenance import BoundarySpan
from python.tests.test_graph_first_cells import L
from python.tests.test_graph_first_rectangle import graph_signature
from python.tests.test_roof_harness import assert_disk
from python.roof_harness import capture

ROOT = Path(__file__).resolve().parents[2]


def abstract_signature(points, loops, features):
    """Read incidence/edge meanings, ignoring disposable interior coordinates."""
    counts = Counter(
        tuple(sorted((a, b))) for f in loops for a, b in zip(f, f[1:] + f[:1])
    )
    boundary = {v for edge, count in counts.items() if count == 1 for v in edge}
    labels = {v: ("boundary", tuple(np.round(points[v][:2], 6))) for v in boundary}
    for v in set(range(len(points))) - boundary:
        ports = [
            next(j for j in edge if j != v)
            for edge, kind in features.items()
            if kind == "ridge" and v in edge
        ]
        if len(ports) != 1 or ports[0] not in boundary:
            raise AssertionError(
                "expected one ridge boundary port per terminal junction"
            )
        labels[v] = ("junction", labels[ports[0]][1])
    faces = []
    for loop in loops:
        ring = tuple(labels[i] for i in loop)
        faces.append(min(ring[i:] + ring[:i] for i in range(len(ring))))
    return sorted(
        (tuple(sorted((labels[a], labels[b]))), kind)
        for (a, b), kind in features.items()
    ), sorted(faces)


def assert_terminal(test, fp, composition):
    """Literal required graph relations, independent of the compositor helper."""
    g = composition.graph
    test.assertEqual((len(g.vertices), len(g.edges), len(g.faces)), (10, 13, 4))
    test.assertEqual(
        Counter(e.kind for e in g.edges),
        {"ridge": 2, "hip": 2, "valley": 1, "eave": 4, "gable_end": 4},
    )
    interior = [i for i, v in enumerate(g.vertices) if v.boundary is None]
    test.assertEqual(len(interior), 2)
    degree = Counter(v for e in g.edges for v in e.vertices)
    test.assertTrue(all(degree[v] == 3 for v in interior))
    test.assertTrue(all(g.vertices[v].cells == (0, 1) for v in interior))
    valley = next(e for e in g.edges if e.kind == "valley")
    corner = next(v for v in valley.vertices if g.vertices[v].boundary is not None)
    np.testing.assert_allclose(
        fp.frame.world_xy(g.vertices[corner].seed), [5.2, 5.6], atol=1e-7
    )
    hips = [e for e in g.edges if e.kind == "hip"]
    test.assertTrue(any(set(e.vertices) == set(interior) for e in hips))
    test.assertEqual(
        {i for e in g.edges if e.boundary for i in e.boundary.original_edges},
        set(range(6)),
    )
    test.assertEqual(Counter(f.cells for f in g.faces), {(0,): 2, (1,): 2})
    assert_disk(
        test,
        SimpleNamespace(
            vertices=[v.seed for v in g.vertices], faces=tuple(f.loop for f in g.faces)
        ),
    )


class TerminalCompositionTests(unittest.TestCase):
    def test_long_similar_width_branches_have_an_interior_initial_embedding(self):
        # An axis-constrained harmonic drawing alone crosses the re-entrant
        # exterior edge for this residential proportion. Independent oracle.
        outline = [
            (0, 0),
            (14.4, 0),
            (14.4, 3.85),
            (3.73, 3.85),
            (3.73, 14.55),
            (0, 14.55),
        ]
        f = analyze(outline)
        g = compose(decompose(f)).graph
        shape = Polygon(f.vertices)
        polygons = [
            Polygon([g.vertices[i].seed for i in face.loop]) for face in g.faces
        ]
        self.assertTrue(all(p.is_valid and p.area > 1e-10 for p in polygons))
        self.assertLess(unary_union(polygons).symmetric_difference(shape).area, 1e-10)
        self.assertLess(abs(sum(p.area for p in polygons) - shape.area), 1e-10)
        self.assertTrue(
            all(
                shape.buffer(1e-10).covers(
                    LineString([g.vertices[i].seed for i in e.vertices])
                )
                for e in g.edges
            )
        )

    def test_alternative_equal_count_partition_keeps_roof_incidence(self):
        # Independently authored other reflex extension of the same outline.
        # This tests composition, not the production partition selector.
        f = analyze(L)
        default = compose(decompose(f)).graph
        ids = {
            tuple(np.round(f.frame.world_xy(p), 6)): i for i, p in enumerate(f.vertices)
        }
        a, b, c, d, e, h = (
            ids[p]
            for p in (
                (0.0, 0.0),
                (14.2, 0.0),
                (14.2, 5.6),
                (5.2, 5.6),
                (5.2, 12.8),
                (0.0, 12.8),
            )
        )
        u = f.frame.direction
        p = np.array([0, 5.6]) - f.frame.origin
        hit = (
            float(p @ [u[0], u[1]]) / f.frame.scale,
            float(p @ [-u[1], u[0]]) / f.frame.scale,
        )
        nodes = f.vertices + (hit,)
        r = len(f.vertices)
        cut = (d, r)
        edge = {source[0]: i for i, source in enumerate(f.source_edges)}
        span = lambda original, lo=0, hi=1: BoundarySpan(
            edge[original], (lo, hi), f.source_edges[edge[original]]
        )
        fraction = (12.8 - 5.6) / 12.8
        host = Cell(
            0,
            (a, b, c, r),
            (a, b, c, d, r),
            (
                Side((a, b), (span(0),), ()),
                Side((b, c), (span(1),), ()),
                Side((c, r), (span(2),), (cut,)),
                Side((r, a), (span(5, fraction, 1),), ()),
            ),
        )
        branch = Cell(
            1,
            (r, d, e, h),
            (r, d, e, h),
            (
                Side((r, d), (), (cut,)),
                Side((d, e), (span(3),), ()),
                Side((e, h), (span(4),), ()),
                Side((h, r), (span(5, 0, fraction),), ()),
            ),
        )
        alternate = Decomposition(
            f, nodes, (host, branch), (Adjacency((0, 1), (2, 0), cut),)
        )
        graph = compose(alternate).graph

        def incidence(g):
            return abstract_signature(
                [f.frame.world_xy(v.seed) for v in g.vertices],
                tuple(face.loop for face in g.faces),
                {e.vertices: e.kind for e in g.edges},
            )

        # Alternate partitions may assign different originating cell IDs.
        self.assertEqual(incidence(graph), incidence(default))

    def test_unequal_width_terminal_graph_primary_and_seed_coverage(self):
        f = analyze(L)
        d = decompose(f)
        c = compose(d)
        g = c.graph
        assert_terminal(self, f, c)
        self.assertEqual(len(c.primitives), 2)
        self.assertTrue(all(len(p.faces) == 2 for p in c.primitives))
        self.assertTrue(
            all(
                len([e for e in p.edges if e.kind == "ridge"]) == 1
                for p in c.primitives
            )
        )
        self.assertEqual(c.connections[0].shared, d.adjacency[0].interval)
        # Geometry oracle is independent and tests only the chosen seed drawing.
        polygons = [
            Polygon([v.seed for v in [g.vertices[i] for i in face.loop]])
            for face in g.faces
        ]
        footprint = Polygon(f.vertices)
        self.assertTrue(all(p.is_valid and p.area > 1e-10 for p in polygons))
        self.assertLess(
            unary_union(polygons).symmetric_difference(footprint).area, 1e-10
        )
        self.assertLess(sum(p.area for p in polygons) - footprint.area, 1e-10)
        for edge in g.edges:
            self.assertTrue(
                footprint.buffer(1e-10).covers(
                    LineString([g.vertices[i].seed for i in edge.vertices])
                ),
                f"{edge.kind} leaves footprint",
            )
        self.assertFalse(any(hasattr(face, "plane") for face in g.faces))

    def test_fixed_graph_has_an_independent_common_pitch_planar_witness(self):
        f = analyze(L)
        g = compose(decompose(f)).graph
        # Exact equal-pitch L witness, not computed by production plane logic.
        ridge_ports = {(14.2, 2.8): 1.4, (2.6, 12.8): 1.3}
        vertices = []
        for i, v in enumerate(g.vertices):
            x, y = f.frame.world_xy(v.seed)
            if v.boundary is not None:
                z = ridge_ports.get((round(x, 6), round(y, 6)), 0)
                vertices.append((x, y, z))
            else:
                port = next(
                    next(j for j in e.vertices if j != i)
                    for e in g.edges
                    if e.kind == "ridge" and i in e.vertices
                )
                px, py = f.frame.world_xy(g.vertices[port].seed)
                vertices.append(
                    (2.8, 2.8, 1.4) if abs(px - 14.2) < 1e-7 else (2.6, 3.0, 1.3)
                )
        supports = {
            0: (0, 0.5, 0),
            2: (0, -0.5, 2.8),
            3: (-0.5, 0, 2.6),
            5: (0.5, 0, 0),
        }
        for face in g.faces:
            source = f.source_edges[face.eaves[0]][0]
            a, b, c = supports[source]
            for i in face.loop:
                x, y, z = vertices[i]
                self.assertAlmostEqual(z, a * x + b * y + c, places=7)
        p = problem(g)
        self.assertEqual(p.variable_xy, p.variable_z)
        self.assertEqual(len(p.variable_xy), 2)
        self.assertEqual(p.faces, tuple(face.loop for face in g.faces))
        self.assertEqual(len(p.ridge_directions), 2)
        for i, z in p.fixed_z:
            self.assertAlmostEqual(vertices[i][2] / f.frame.scale, z, places=8)
        self.assertNotEqual(
            tuple(v[:2] for v in vertices),
            tuple(f.frame.world_xy(v.seed) for v in g.vertices),
        )
        with self.assertRaisesRegex(UnsupportedRoofError, "awaits nonlinear solve"):
            solve_rectangle(g)
        with self.assertRaisesRegex(UnsupportedRoofError, "nonplanar"):
            RoofMesh(g, p.initial_vertices)
        # A valid solver result is exported against exactly the same graph.
        u = f.frame.direction
        solved = tuple(
            (
                (x - f.frame.origin[0]) * u[0] / f.frame.scale
                + (y - f.frame.origin[1]) * u[1] / f.frame.scale,
                -(x - f.frame.origin[0]) * u[1] / f.frame.scale
                + (y - f.frame.origin[1]) * u[0] / f.frame.scale,
                z / f.frame.scale,
            )
            for x, y, z in vertices
        )
        mesh = RoofMesh(g, solved)
        self.assertIs(mesh.graph, g)
        self.assertEqual(mesh.faces, p.faces)

    def test_existing_semantic_harness_secondary_topology_comparison(self):
        f = analyze(L)
        g = compose(decompose(f)).graph
        old = capture(
            {"name": "orthogonal_L", "footprint": L, "roof_type": "gable", "pitch": 0.5}
        )
        legacy = abstract_signature(
            old["vertices"],
            tuple(tuple(x["loop"]) for x in old["faces"]),
            {tuple(e["vertices"]): e["feature"] for e in old["edge_features"]},
        )
        points = [
            np.array(f.frame.world_xy(v.seed)) / f.frame.scale for v in g.vertices
        ]
        new = abstract_signature(
            points,
            tuple(face.loop for face in g.faces),
            {e.vertices: e.kind for e in g.edges},
        )
        self.assertEqual(new, legacy)

    def test_primary_proof_detects_changed_valley_semantics(self):
        f = analyze(L)
        c = compose(decompose(f))
        g = c.graph
        i = next(i for i, e in enumerate(g.edges) if e.kind == "valley")
        wrong = replace(
            g, edges=g.edges[:i] + (replace(g.edges[i], kind="hip"),) + g.edges[i + 1 :]
        )
        with self.assertRaises(AssertionError):
            assert_terminal(self, f, replace(c, graph=wrong))

    def test_graph_metamorphisms_and_source_edge_geometry(self):
        f = analyze(L)
        g = compose(decompose(f)).graph
        reference = graph_signature(f, g)
        angle = 0.693
        r = np.array(
            [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
        )
        split = []
        for a, b in zip(L, np.roll(L, -1, axis=0)):
            split.extend((a, (a + b) / 2))
        variants = [
            (L + [370, -289], np.eye(2), np.array([370, -289])),
            (L @ r.T, r, np.zeros(2)),
            (np.roll(L, 2, axis=0), np.eye(2), np.zeros(2)),
            (L[::-1], np.eye(2), np.zeros(2)),
            (split, np.eye(2), np.zeros(2)),
        ]
        for points, rotation, offset in variants:
            f = analyze(points)
            c = compose(decompose(f))
            g = c.graph
            self.assertEqual(graph_signature(f, g, rotation, offset), reference)
            self.assertEqual(
                {i for e in g.edges if e.boundary for i in e.boundary.original_edges},
                set(range(len(points))),
            )
            raw = np.asarray(points)
            for edge in g.edges:
                if edge.boundary is None:
                    continue
                segment = np.array(
                    [f.frame.world_xy(g.vertices[i].seed) for i in edge.vertices]
                )
                for original in edge.boundary.original_edges:
                    a, b = raw[original], raw[(original + 1) % len(raw)]
                    v = b - a
                    q = segment - a
                    self.assertLess(
                        max(abs(v[0] * q[:, 1] - v[1] * q[:, 0])) / np.linalg.norm(v),
                        1e-7,
                    )

    def test_equal_width_and_opposite_width_order_use_the_same_graft(self):
        for points, expected in [
            (
                [(0, 0), (14, 0), (14, 5), (5, 5), (5, 12), (0, 12)],
                {"ridge": 2, "hip": 1, "valley": 1, "eave": 4, "gable_end": 4},
            ),
            (
                [(0, 0), (16, 0), (16, 4.8), (5.6, 4.8), (5.6, 14), (0, 14)],
                {"ridge": 2, "hip": 2, "valley": 1, "eave": 4, "gable_end": 4},
            ),
        ]:
            f = analyze(points)
            c = compose(decompose(f))
            g = c.graph
            self.assertEqual(Counter(e.kind for e in g.edges), expected)
            degree = Counter(v for e in g.edges for v in e.vertices)
            self.assertEqual(
                sorted(
                    degree[i] for i, v in enumerate(g.vertices) if v.boundary is None
                ),
                [4] if expected["hip"] == 1 else [3, 3],
            )
            assert_disk(
                self,
                SimpleNamespace(
                    vertices=[v.seed for v in g.vertices],
                    faces=tuple(face.loop for face in g.faces),
                ),
            )

    def test_new_L_route_runs_without_shapely_or_legacy(self):
        script = """import sys,builtins
sys.path.insert(0,sys.argv[1])
sys.path.insert(0,sys.argv[1] + "/addon")
original=builtins.__import__
def checked(name,*args,**kwargs):
 if name=="shapely" or name.startswith(("shapely.","numpy.","roof_generator.core.roof_")):raise AssertionError("forbidden new-path import: "+name)
 return original(name,*args,**kwargs)
builtins.__import__=checked
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose
from roof_generator.core.topology import compose
from roof_generator.core.solve import problem
g=compose(decompose(analyze(((0,0),(14.2,0),(14.2,5.6),(5.2,5.6),(5.2,12.8),(0,12.8))))).graph
assert len(g.faces)==4 and len(problem(g).variable_xy)==2
"""
        p = subprocess.run(
            [sys.executable, "-I", "-c", script, str(ROOT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p.returncode, 0, p.stderr)


if __name__ == "__main__":
    unittest.main()
