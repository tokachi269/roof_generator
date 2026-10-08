# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent analytic proofs plus secondary semantic regression evidence."""

from collections import defaultdict
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "addon"))
sys.path.insert(0, str(ROOT))
from python.roof_harness import capture, cases, differences, snapshot
from roof_generator.core.generation import generate_roof, GenerationSettings
from types import SimpleNamespace

BASELINE = Path(__file__).parent / "fixtures/roof_mesh_semantics.json"


def assert_disk(test, mesh):
    """Independent combinatorial proof using only exported vertices/face loops."""
    edges = defaultdict(list)
    links = defaultdict(lambda: defaultdict(set))
    used = set()
    for fi, face in enumerate(mesh.faces):
        test.assertGreaterEqual(len(face), 3, "face collapsed")
        test.assertEqual(len(set(face)), len(face), "repeated face vertex")
        for i, a in enumerate(face):
            used.add(a)
            b = face[(i + 1) % len(face)]
            edges[tuple(sorted((a, b)))].append((fi, a, b))
            previous = face[i - 1]
            links[a][previous].add(b)
            links[a][b].add(previous)
    test.assertEqual(used, set(range(len(mesh.vertices))), "unreferenced vertices")
    neighbours = {i: set() for i in range(len(mesh.faces))}
    boundary = defaultdict(set)
    for (a, b), owners in edges.items():
        test.assertIn(len(owners), (1, 2), "nonmanifold edge")
        if len(owners) == 2:
            (i, u, v), (j, x, y) = owners
            test.assertEqual((u, v), (y, x), "face winding inconsistent")
            neighbours[i].add(j)
            neighbours[j].add(i)
        else:
            boundary[a].add(b)
            boundary[b].add(a)

    def connected(graph):
        test.assertTrue(graph, "empty topology")
        seen, pending = set(), [next(iter(graph))]
        while pending:
            current = pending.pop()
            if current not in seen:
                seen.add(current)
                pending.extend(graph[current] - seen)
        test.assertEqual(seen, set(graph), "disconnected topology")

    connected(neighbours)
    connected(boundary)
    test.assertTrue(
        all(len(adjacent) == 2 for adjacent in boundary.values()),
        "boundary is not one manifold loop",
    )
    for vertex, link in links.items():
        connected(link)
        degrees = [len(adjacent) for adjacent in link.values()]
        if vertex in boundary:
            test.assertEqual(degrees.count(1), 2, "boundary vertex fan is not a path")
            test.assertTrue(all(d in (1, 2) for d in degrees))
        else:
            test.assertTrue(
                all(d == 2 for d in degrees), "interior vertex fan is not a cycle"
            )
    test.assertEqual(
        len(mesh.vertices) - len(edges) + len(mesh.faces),
        1,
        "Euler characteristic is not a disk",
    )


def assert_rectangle(test, result, kind, pitch=0.5, eave=2.0):
    """12x6 analytic min of edge-distance slopes; no production helpers."""
    mesh = result.mesh
    if hasattr(result, "generation"):
        mesh = world_mesh(result)
    vertices = np.asarray(mesh.vertices)
    x, y, z = vertices.T
    supports = [y, 6 - y] if kind == "gable" else [x, 12 - x, y, 6 - y]
    expected_z = eave + pitch * np.min(supports, axis=0)
    np.testing.assert_allclose(
        z, expected_z, atol=1e-6, rtol=0, err_msg="analytic roof height"
    )
    test.assertAlmostEqual(float(z.max()), eave + pitch * 3, delta=1e-6)
    test.assertEqual(
        len(mesh.faces), 2 if kind == "gable" else 4, "exposed planar face count"
    )
    projected = []
    for face in mesh.faces:
        points = vertices[list(face)]
        poly = Polygon(points[:, :2])
        test.assertTrue(poly.is_valid)
        test.assertGreater(poly.area, 0)
        projected.append(poly)
        # Each full face must belong to one independent affine support plane.
        plane_heights = [eave + pitch * s[list(face)] for s in supports]
        test.assertTrue(
            any(np.max(np.abs(points[:, 2] - h)) < 1e-6 for h in plane_heights),
            "face is not on an analytic roof plane",
        )
    cover = unary_union(projected)
    rectangle = Polygon([(0, 0), (12, 0), (12, 6), (0, 6)])
    test.assertLess(
        cover.symmetric_difference(rectangle).area, 1e-5, "footprint coverage"
    )
    test.assertLess(
        abs(sum(poly.area for poly in projected) - 72), 1e-5, "overlap/projected area"
    )
    test.assertAlmostEqual(cover.length, 36, delta=1e-5)
    features = defaultdict(list)
    for (a, b), feature in mesh.edge_features.items():
        features[feature].append(vertices[[a, b]])
    test.assertEqual(len(features["ridge"]), 1, "one analytic ridge")
    expected_ridge = (
        np.array([[0, 3, eave + pitch * 3], [12, 3, eave + pitch * 3]])
        if kind == "gable"
        else np.array([[3, 3, eave + pitch * 3], [9, 3, eave + pitch * 3]])
    )
    ridge = sorted(features["ridge"][0].tolist())
    np.testing.assert_allclose(
        ridge, expected_ridge, atol=1e-6, rtol=0, err_msg="ridge location/height"
    )
    test.assertEqual(
        set(features),
        {"ridge", "eave", "gable_end"} if kind == "gable" else {"ridge", "eave", "hip"},
    )
    test.assertEqual(len(features["eave"]), 2 if kind == "gable" else 4)
    if kind == "hip":
        test.assertEqual(len(features["hip"]), 4)
    for segment in features["eave"]:
        np.testing.assert_allclose(segment[:, 2], eave, atol=1e-6, rtol=0)
    assert_disk(test, mesh)


def world_mesh(result):
    fp = result.generation.footprint
    return SimpleNamespace(
        vertices=tuple(fp.frame.world_xyz(p) for p in result.mesh.vertices),
        faces=result.mesh.faces,
        edge_features=result.mesh.edge_features,
    )


class RoofHarnessTests(unittest.TestCase):
    def test_frozen_rectangle_mesh_semantics_without_old_runtime(self):
        frozen = json.loads(BASELINE.read_text())["cases"]
        for name, expected in frozen.items():
            case = next(c for c in cases() if c["name"] == name)
            self.assertEqual(differences(expected, capture(case)), [], name)

    def test_analytic_primary_proofs_and_independent_fault_detection(self):
        for kind in ("gable", "hip"):
            r = generate_roof(
                ((0, 0), (12, 0), (12, 6), (0, 6)),
                GenerationSettings(kind, eave_height=2),
            )
            m = world_mesh(r)
            assert_rectangle(self, SimpleNamespace(mesh=m), kind)
            points = list(m.vertices)
            i = max(range(len(points)), key=lambda i: points[i][2])
            points[i] = (*points[i][:2], points[i][2] + 0.1)
            bad = SimpleNamespace(
                vertices=tuple(points), faces=m.faces, edge_features=m.edge_features
            )
            with self.assertRaises(AssertionError):
                assert_rectangle(self, SimpleNamespace(mesh=bad), kind)
            bad = SimpleNamespace(
                vertices=m.vertices, faces=m.faces[:-1], edge_features=m.edge_features
            )
            with self.assertRaises(AssertionError):
                assert_rectangle(self, SimpleNamespace(mesh=bad), kind)

    def test_current_mesh_semantics_transform_and_source_provenance(self):
        angle = 0.371
        c, s = np.cos(angle), np.sin(angle)
        rot = np.array([[c, -s], [s, c]])
        raw = np.array(((0, 0), (12, 0), (12, 6), (0, 6)), float)
        for kind in ("gable", "hip", "shed", "flat"):
            reference = snapshot(generate_roof(raw, GenerationSettings(kind)))
            variants = (
                (raw[::-1], None, None, (1, 0)),
                (np.roll(raw, 2, axis=0), None, None, (1, 0)),
                (raw + [147, -293], None, [147, -293], (1, 0)),
                (raw @ rot.T, rot, None, (c, s)),
            )
            for points, r, t, direction in variants:
                result = generate_roof(
                    points, GenerationSettings(kind, reference_direction=direction)
                )
                self.assertEqual(
                    differences(reference, snapshot(result, rotation=r, translation=t)),
                    [],
                )
                fp = result.generation.footprint
                self.assertEqual(
                    {i for edges in fp.source_edges for i in edges},
                    set(range(len(points))),
                )

    def test_snapshot_comparison_detects_real_changes(self):
        reference = capture(cases()[0])
        near = deepcopy(reference)
        near["vertices"][0][0] += 1e-10
        self.assertEqual(differences(reference, near), [])
        for field in (
            "vertices",
            "faces",
            "edge_features",
            "normalized_footprint",
            "projected_area",
            "perimeter",
        ):
            changed = deepcopy(reference)
            if isinstance(changed[field], list):
                changed[field] = changed[field][:-1]
            else:
                changed[field] += 1
            self.assertTrue(differences(reference, changed))


if __name__ == "__main__":
    unittest.main()
