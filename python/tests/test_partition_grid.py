# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent minimum, rectangle coverage, incidence and provenance proofs."""

from collections import Counter, defaultdict
from dataclasses import replace
from functools import lru_cache
import json
import math
from pathlib import Path
import subprocess
import sys
import python
import unittest

import numpy as np
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose
from roof_generator.core.errors import UnsupportedRoofError
from python.tests.grid_footprints import generated
from python.tests.test_rectangle_partition import oracle_diagonals

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = json.loads(
    (ROOT / "python/tests/fixtures/rectangle_partition.json").read_text()
)


def oracle_minimum(points):
    """Pair/GEOS visibility + exhaustive bitset MIS; no production helpers."""
    reflex, diagonals = oracle_diagonals(points)
    lines = [LineString(d) for d in diagonals]
    conflicts = [
        sum(1 << j for j, q in enumerate(lines) if j != i and p.intersects(q))
        for i, p in enumerate(lines)
    ]

    @lru_cache(None)
    def independent(mask):
        if not mask:
            return 0
        vertices = [i for i in range(len(lines)) if mask & (1 << i)]
        v = max(vertices, key=lambda i: (conflicts[i] & mask).bit_count())
        if not (conflicts[v] & mask):
            return 1 + independent(mask & ~(1 << v))
        return max(
            independent(mask & ~(1 << v)),
            1 + independent(mask & ~((1 << v) | conflicts[v])),
        )

    size = independent((1 << len(lines)) - 1)
    return len(reflex) - size + 1, len(reflex), len(diagonals), size


def assert_partition(test, points, decomposition, minimum):
    """Output-reading Primary proof; GEOS never chooses production cuts."""
    d = decomposition
    fp = d.footprint
    nodes = np.asarray([fp.frame.world_xy(p) for p in d.vertices])
    shape = Polygon(points)
    cells = [Polygon(nodes[list(c.boundary)]) for c in d.cells]
    test.assertEqual(len(cells), minimum)
    test.assertEqual(d.certificate.minimum_cells, minimum)
    test.assertTrue(all(p.is_valid and p.area > 1e-8 for p in cells))
    for cell in d.cells:
        test.assertEqual((len(cell.corners), len(cell.sides)), (4, 4))
        p = nodes[list(cell.corners)]
        v = np.roll(p, -1, axis=0) - p
        test.assertTrue(
            all(
                abs(float(v[i] @ v[(i + 1) % 4]))
                < 1e-7 * np.linalg.norm(v[i]) * np.linalg.norm(v[(i + 1) % 4])
                for i in range(4)
            )
        )
        test.assertLess(Polygon(p).symmetric_difference(cells[cell.id]).area, 1e-8)
    union = unary_union(cells)
    test.assertLess(shape.symmetric_difference(union).area, 1e-7)
    test.assertLess(abs(sum(p.area for p in cells) - union.area), 1e-7)
    incidence = defaultdict(list)
    spans = defaultdict(list)
    artificial = defaultdict(list)
    provenance = set()
    for cell in d.cells:
        for a, b in zip(cell.boundary, cell.boundary[1:] + cell.boundary[:1]):
            incidence[tuple(sorted((a, b)))].append((cell.id, a, b))
        for index, side in enumerate(cell.sides):
            line = LineString(nodes[list(side.vertices)])
            for edge in side.artificial:
                test.assertGreater(LineString(nodes[list(edge)]).length, 1e-8)
                test.assertTrue(line.buffer(1e-7).covers(LineString(nodes[list(edge)])))
                artificial[edge].append((cell.id, index))
            for span in side.exterior:
                spans[span.edge].append(span.interval)
                provenance.update(span.original_edges)
                a = np.asarray(fp.frame.world_xy(fp.vertices[span.edge]))
                b = np.asarray(
                    fp.frame.world_xy(fp.vertices[(span.edge + 1) % len(fp.vertices)])
                )
                interval = LineString([a + t * (b - a) for t in span.interval])
                test.assertTrue(line.buffer(1e-7).covers(interval))
                test.assertTrue(shape.boundary.buffer(1e-7).covers(interval))
                test.assertEqual(span.original_edges, fp.source_edges[span.edge])
    test.assertEqual(provenance, set(range(len(points))))
    test.assertEqual(set(spans), set(range(len(fp.vertices))))
    for values in spans.values():
        values.sort()
        test.assertAlmostEqual(values[0][0], 0, places=8)
        test.assertAlmostEqual(values[-1][1], 1, places=8)
        test.assertTrue(
            all(abs(a[1] - b[0]) < 1e-8 for a, b in zip(values, values[1:]))
        )
    test.assertTrue(all(len(owners) == 2 for owners in artificial.values()))
    test.assertEqual(set(artificial), {a.interval for a in d.adjacency})
    test.assertEqual(len(artificial), len(d.adjacency))
    for key, owners in incidence.items():
        test.assertEqual(len(owners), 2 if key in artificial else 1)
        if len(owners) == 2:
            test.assertEqual(owners[0][1:], owners[1][1:][::-1])
    shared = defaultdict(list)
    for a in d.adjacency:
        test.assertEqual(sorted(artificial[a.interval]), list(zip(a.cells, a.sides)))
        line = LineString(nodes[list(a.interval)])
        for cell in a.cells:
            test.assertTrue(cells[cell].boundary.buffer(1e-7).covers(line))
        shared[a.cells].append(line)
    for a in range(len(cells)):
        for b in range(a + 1, len(cells)):
            intersection = cells[a].boundary.intersection(cells[b].boundary)
            if intersection.length < 1e-7:
                continue
            test.assertIn((a, b), shared)
            test.assertLess(
                intersection.symmetric_difference(unary_union(shared[a, b])).length,
                1e-7,
            )
    degree = Counter(v for edge in incidence for v in edge)
    test.assertTrue(all(degree[v] >= 2 for v in range(len(nodes))))
    test.assertTrue(all(degree[v] >= 3 for v in d.certificate.reflex))
    test.assertEqual(len(nodes) - len(incidence) + len(cells), 1)
    chosen = [
        LineString(nodes[list(d.certificate.selection.diagonals[i].endpoints)])
        for i in d.certificate.selection.selected
    ]
    test.assertTrue(
        all(not a.intersects(b) for i, a in enumerate(chosen) for b in chosen[:i])
    )


def cell_signature(d, rotation=np.eye(2), offset=np.zeros(2)):
    return tuple(
        sorted(
            tuple(
                sorted(
                    tuple(np.round(p, 6))
                    for p in (
                        np.asarray(
                            [
                                d.footprint.frame.world_xy(d.vertices[i])
                                for i in c.corners
                            ]
                        )
                        - offset
                    )
                    @ rotation
                )
            )
            for c in d.cells
        )
    )


def symmetric_signatures(points, signature):
    """Only genuine outline rotational automorphisms, not arbitrary test slack."""
    raw = np.asarray(points, dtype=float)
    center = (raw.min(axis=0) + raw.max(axis=0)) / 2
    shape = Polygon(raw)
    keys = set()
    for r in (
        np.eye(2),
        np.array([[0, -1], [1, 0]]),
        -np.eye(2),
        np.array([[0, 1], [-1, 0]]),
    ):
        if (
            Polygon((raw - center) @ r.T + center).symmetric_difference(shape).area
            > 1e-8
        ):
            continue
        keys.add(
            tuple(
                sorted(
                    tuple(
                        sorted(
                            tuple(np.round((np.asarray(p) - center) @ r.T + center, 6))
                            for p in c
                        )
                    )
                    for c in signature
                )
            )
        )
    return keys


class GeneratedPartitionTests(unittest.TestCase):
    def test_known_literal_minima_and_full_cell_contract(self):
        for c in FIXTURES:
            with self.subTest(name=c["name"]):
                points = c["footprint"]
                expected = c["minimum_cells"]
                self.assertEqual(oracle_minimum(points)[0], expected)
                d = decompose(analyze(points))
                self.assertEqual(d, decompose(analyze(points)))
                assert_partition(self, points, d, expected)

    def test_interior_steiner_junction_is_noded_in_all_three_cell_boundaries(self):
        case = next(c for c in FIXTURES if c["name"] == "interior_steiner")
        fp = analyze(case["footprint"])
        d = decompose(fp)
        assert_partition(self, case["footprint"], d, 3)
        nodes = [fp.frame.world_xy(p) for p in d.vertices]
        joint = next(
            i
            for i, p in enumerate(nodes)
            if np.linalg.norm(np.asarray(p) - [3, 1]) < 1e-8
        )
        self.assertGreaterEqual(joint, len(fp.vertices))
        self.assertEqual(sum(joint in c.boundary for c in d.cells), 3)
        self.assertEqual(
            sum(joint in c.boundary and joint not in c.corners for c in d.cells), 1
        )
        self.assertEqual(len(d.adjacency), 3)
        # Interior T junctions induce a cycle in the cell dual. Do not assume
        # every valid hole-free partition's adjacency is a tree.
        self.assertEqual({a.cells for a in d.adjacency}, {(0, 1), (0, 2), (1, 2)})
        self.assertEqual(sum(joint in a.interval for a in d.adjacency), 3)

    def test_five_hundred_unknown_connected_grid_shapes(self):
        counts = Counter()
        for index, points in enumerate(generated()):
            with self.subTest(index=index, points=points):
                minimum, reflex, diagonals, independent = oracle_minimum(points)
                d = decompose(analyze(points))
                s = d.certificate.selection
                self.assertEqual(
                    (len(d.certificate.reflex), len(s.diagonals), len(s.selected)),
                    (reflex, diagonals, independent),
                )
                self.assertEqual(len(s.matching), diagonals - independent)
                assert_partition(self, points, d, minimum)
                counts[len(points)] += 1
        self.assertEqual(sum(counts.values()), 500)
        self.assertTrue(all(counts[n] > 0 for n in (14, 20, 40)))

    def test_rigid_cyclic_winding_and_collinear_metamorphisms(self):
        angle = 0.619
        r = np.array(
            [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
        )
        samples = [c["footprint"] for c in FIXTURES] + list(generated(20, seed=143))
        for raw in samples:
            points = np.asarray(raw, float)
            base = decompose(analyze(points))
            expected = cell_signature(base)
            allowed = symmetric_signatures(points, expected)
            split = []
            for a, b in zip(points, np.roll(points, -1, axis=0)):
                split.extend((a, (a + b) / 2))
            variants = [
                (points + [431, -187], np.eye(2), np.array([431, -187])),
                (points @ r.T, r, np.zeros(2)),
                (np.roll(points, 3, axis=0), np.eye(2), np.zeros(2)),
                (points[::-1], np.eye(2), np.zeros(2)),
                (split, np.eye(2), np.zeros(2)),
            ]
            for raw, rotation, offset in variants:
                with self.subTest(points=points.tolist()):
                    d = decompose(analyze(raw))
                    assert_partition(self, raw, d, len(base.cells))
                    self.assertIn(cell_signature(d, rotation, offset), allowed)
                    if len(allowed) == 1:
                        self.assertEqual(cell_signature(d, rotation, offset), expected)

    def test_primary_oracle_detects_missing_adjacency_and_exterior_provenance(self):
        points = FIXTURES[2]["footprint"]
        d = decompose(analyze(points))
        with self.assertRaises(AssertionError):
            assert_partition(self, points, replace(d, adjacency=()), 2)
        cell = d.cells[0]
        side = next(s for s in cell.sides if s.exterior)
        span = side.exterior[0]
        wrong = replace(
            side, exterior=(replace(span, original_edges=()),) + side.exterior[1:]
        )
        sides = tuple(wrong if s is side else s for s in cell.sides)
        with self.assertRaises(AssertionError):
            assert_partition(
                self,
                points,
                replace(d, cells=(replace(cell, sides=sides),) + d.cells[1:]),
                2,
            )

    def test_runtime_is_roof_independent_and_without_third_party_imports(self):
        script = """import sys,builtins,json
sys.path.insert(0,sys.argv[1])
sys.path.insert(0,sys.argv[1] + "/addon")
original=builtins.__import__
def checked(name,*args,**kwargs):
 if name.startswith(('shapely','numpy','roof_generator.core.roof_','roof_generator.core.topology','roof_generator.core.solve')):raise AssertionError('forbidden partition import: '+name)
 return original(name,*args,**kwargs)
builtins.__import__=checked
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose
for c in json.load(open(sys.argv[2])):
 d=decompose(analyze(c['footprint']))
 assert len(d.cells)==c['minimum_cells']
"""
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                script,
                str(ROOT),
                str(ROOT / "python/tests/fixtures/rectangle_partition.json"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unsupported_input_is_not_rectified_or_repaired(self):
        for points in [
            [(0, 0), (8, 0), (9, 4), (0, 4)],
            [(0, 0), (2, 0), (2, 2), (1, 2), (1, 0), (3, 0), (3, 3), (0, 3)],
            [(0, 0), (2, 2), (0, 2), (2, 0)],
            [[(0, 0), (5, 0), (5, 5), (0, 5)], [(1, 1), (1, 2), (2, 2), (2, 1)]],
        ]:
            with self.assertRaises(UnsupportedRoofError):
                decompose(analyze(points))


if __name__ == "__main__":
    unittest.main()
