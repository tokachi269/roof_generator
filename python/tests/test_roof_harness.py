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
from roof_generator.core.roof_building import generate_roof
from roof_generator.core.roof_parts import RoofParameters

BASELINE = Path(__file__).parent / "fixtures/roof_semantic_baseline.json"


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
    test.assertTrue(all(len(adjacent) == 2 for adjacent in boundary.values()), "boundary is not one manifold loop")
    for vertex, link in links.items():
        connected(link)
        degrees = [len(adjacent) for adjacent in link.values()]
        if vertex in boundary:
            test.assertEqual(degrees.count(1), 2, "boundary vertex fan is not a path")
            test.assertTrue(all(d in (1, 2) for d in degrees))
        else:
            test.assertTrue(all(d == 2 for d in degrees), "interior vertex fan is not a cycle")
    test.assertEqual(len(mesh.vertices) - len(edges) + len(mesh.faces), 1, "Euler characteristic is not a disk")


def assert_rectangle(test, result, kind, pitch=0.5, eave=2.0):
    """12x6 analytic min of edge-distance slopes; no production helpers."""
    mesh = result.mesh
    vertices = np.asarray(mesh.vertices)
    x, y, z = vertices.T
    supports = [y, 6 - y] if kind == "gable" else [x, 12 - x, y, 6 - y]
    expected_z = eave + pitch * np.min(supports, axis=0)
    np.testing.assert_allclose(z, expected_z, atol=1e-6, rtol=0, err_msg="analytic roof height")
    test.assertAlmostEqual(float(z.max()), eave + pitch * 3, delta=1e-6)
    test.assertEqual(len(mesh.faces), 2 if kind == "gable" else 4, "exposed planar face count")
    projected = []
    for face in mesh.faces:
        points = vertices[list(face)]
        poly = Polygon(points[:, :2])
        test.assertTrue(poly.is_valid)
        test.assertGreater(poly.area, 0)
        projected.append(poly)
        # Each full face must belong to one independent affine support plane.
        plane_heights = [eave + pitch * s[list(face)] for s in supports]
        test.assertTrue(any(np.max(np.abs(points[:, 2] - h)) < 1e-6 for h in plane_heights), "face is not on an analytic roof plane")
    cover = unary_union(projected)
    rectangle = Polygon([(0, 0), (12, 0), (12, 6), (0, 6)])
    test.assertLess(cover.symmetric_difference(rectangle).area, 1e-5, "footprint coverage")
    test.assertLess(abs(sum(poly.area for poly in projected) - 72), 1e-5, "overlap/projected area")
    test.assertAlmostEqual(cover.length, 36, delta=1e-5)
    features = defaultdict(list)
    for (a, b), feature in mesh.edge_features.items():
        features[feature].append(vertices[[a, b]])
    test.assertEqual(len(features["ridge"]), 1, "one analytic ridge")
    expected_ridge = np.array([[0, 3, eave + pitch * 3], [12, 3, eave + pitch * 3]]) if kind == "gable" else np.array([[3, 3, eave + pitch * 3], [9, 3, eave + pitch * 3]])
    ridge = sorted(features["ridge"][0].tolist())
    np.testing.assert_allclose(ridge, expected_ridge, atol=1e-6, rtol=0, err_msg="ridge location/height")
    test.assertEqual(set(features), {"ridge", "eave", "gable_end"} if kind == "gable" else {"ridge", "eave", "hip"})
    test.assertEqual(len(features["eave"]), 2 if kind == "gable" else 4)
    if kind == "hip":
        test.assertEqual(len(features["hip"]), 4)
    for segment in features["eave"]:
        np.testing.assert_allclose(segment[:, 2], eave, atol=1e-6, rtol=0)
    assert_disk(test, mesh)


def assert_provenance(test, result, original):
    """Provenance must refer to actual input segments, not just matching IDs."""
    original = np.asarray(original, float)
    frame = result.footprint.frame
    u = np.asarray(frame.u)
    basis = np.column_stack((u, [-u[1], u[0]]))
    normalized_boundary = np.asarray(result.footprint.polygon.exterior.coords)[:-1]
    seen = set()
    for part in result.topology.parts:
        for source in part.source_edges:
            segment = np.asarray(source.segment) @ basis.T * frame.scale + frame.origin
            test.assertTrue(source.original_edges, "empty provenance")
            for i in source.original_edges:
                test.assertTrue(0 <= i < len(original), "nonexistent source edge")
                seen.add(i)
                a, b = original[i], original[(i + 1) % len(original)]
                direction = b - a
                # original_edges identifies the entire normalized exterior
                # edge, not just this part's exposed subsegment.
                offset = segment - a
                distance = np.abs(direction[0] * offset[:, 1] - direction[1] * offset[:, 0]) / np.linalg.norm(direction)
                test.assertLess(float(distance.max()), 1e-5, "source points off input edge")
                j = source.footprint_edge
                parent = normalized_boundary[[j, (j + 1) % len(normalized_boundary)]] @ basis.T * frame.scale + frame.origin
                vector = parent[1] - parent[0]
                t = (np.asarray([a, b]) - parent[0]) @ vector / (vector @ vector)
                test.assertGreaterEqual(float(t.min()), -1e-6, "original edge outside provenance parent")
                test.assertLessEqual(float(t.max()), 1 + 1e-6, "original edge outside provenance parent")
                partial_t = (segment - parent[0]) @ vector / (vector @ vector)
                test.assertGreaterEqual(float(partial_t.min()), -1e-6)
                test.assertLessEqual(float(partial_t.max()), 1 + 1e-6)
    test.assertEqual(seen, set(range(len(original))), "exterior provenance lost")


class RoofHarnessTests(unittest.TestCase):
    def test_analytic_rectangle_gable_and_hip_primary_proofs(self):
        for kind in ("gable", "hip"):
            with self.subTest(kind=kind):
                result = generate_roof([(0, 0), (12, 0), (12, 6), (0, 6)], RoofParameters(kind, pitch=0.5, eave_height=2))
                assert_rectangle(self, result, kind)

    def test_primary_proof_detects_height_feature_and_missing_face_faults(self):
        result = generate_roof([(0, 0), (12, 0), (12, 6), (0, 6)], RoofParameters("gable", eave_height=2))
        vertices = list(result.mesh.vertices)
        i = max(range(len(vertices)), key=lambda i: vertices[i][2])
        vertices[i] = (*vertices[i][:2], vertices[i][2] + 0.1)
        features = dict(result.mesh.edge_features)
        ridge = next(edge for edge, kind in features.items() if kind == "ridge")
        features[ridge] = "valley"
        faults = [replace(result.mesh, vertices=tuple(vertices)), replace(result.mesh, edge_features=features), replace(result.mesh, faces=result.mesh.faces[:-1])]
        for fault in faults:
            with self.subTest(fault=fault), self.assertRaises(AssertionError):
                assert_rectangle(self, replace(result, mesh=fault), "gable")

    def test_semantic_baseline_secondary_differential(self):
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(set(baseline["cases"]), {case["name"] for case in cases()})
        for case in cases():
            with self.subTest(case=case["name"]):
                actual = capture(case)
                self.assertEqual(differences(baseline["cases"][case["name"]], actual), [])
                if "expected_parts" in case and "max_states" not in case and "overrides" not in case:
                    self.assertEqual(actual["status"], "ok")
                    self.assertEqual(actual["part_count"], case["expected_parts"])
                elif case["name"].startswith(("invalid_", "unsupported_", "exhausted_")):
                    self.assertEqual(actual, {"status": "unsupported", "failure_class": "UnsupportedRoofError"})

    def test_snapshot_comparator_detects_changes_and_accepts_small_roundoff(self):
        reference = capture(cases()[0])
        near = deepcopy(reference)
        near["vertices"][0][0] += 1e-10
        self.assertEqual(differences(reference, near), [])
        for field in ("part_count", "parts", "regions", "vertices", "faces", "edge_features", "normalized_footprint", "projected_area", "perimeter"):
            changed = deepcopy(reference)
            if isinstance(changed[field], list):
                changed[field] = changed[field][:-1]
            else:
                changed[field] += 1
            with self.subTest(field=field):
                self.assertTrue(differences(reference, changed), "semantic change went undetected")

    def test_cyclic_start_and_winding_semantics_all_acceptance_cases(self):
        for case in cases()[:16]:
            points = np.asarray(case["footprint"], float)
            params = RoofParameters(case["roof_type"], pitch=case["pitch"])
            original = generate_roof(points, params)
            reference = snapshot(original)
            for label, transformed in (("cyclic", np.roll(points, 2, axis=0)), ("winding", points[::-1])):
                with self.subTest(case=case["name"], transform=label):
                    result = generate_roof(transformed, params)
                    errors = differences(reference, snapshot(result))
                    if case["name"] == "rectangle_shed" and label == "cyclic":
                        # Known baseline ambiguity, not a passing invariance.
                        # Do not silently change directional roof semantics in
                        # the behavior-preserving harness milestone.
                        self.assertTrue(any("planes" in error for error in errors), "baseline directional ambiguity changed; review roof semantics")
                        self.assertTrue(any("vertices" in error for error in errors))
                        xyz = np.asarray(result.mesh.vertices)
                        np.testing.assert_allclose(xyz[:, 2], case["pitch"] * (6.2 - xyz[:, 1]), atol=1e-6, rtol=0, err_msg="known cyclic shed direction differs from baseline")
                    else:
                        self.assertEqual(errors, [])
                    assert_provenance(self, result, transformed)

    def test_full_semantic_rigid_and_collinear_metamorphic(self):
        # Existing tests compare mesh incidence only. Here compare planes,
        # exposed regions, adjacency and geometric exterior provenance too.
        for name in ("rectangle_gable", "oblique_L", "residential_multi_reflex"):
            case = next(c for c in cases() if c["name"] == name)
            points = np.asarray(case["footprint"], float)
            params = RoofParameters(case["roof_type"], pitch=case["pitch"])
            reference = snapshot(generate_roof(points, params))
            angle = 0.371
            rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
            translation = np.array([147.381, -293.126])
            variants = (("translation", points + translation, None, translation), ("rotation", points @ rotation.T, rotation, None))
            for label, transformed, r, t in variants:
                with self.subTest(case=name, transform=label):
                    result = generate_roof(transformed, params)
                    self.assertEqual(differences(reference, snapshot(result, rotation=r, translation=t)), [])
                    assert_provenance(self, result, transformed)
            subdivided = [p for a, b in zip(points, np.roll(points, -1, axis=0)) for p in (a, a + (b - a) * 0.37)]
            with self.subTest(case=name, transform="collinear"):
                result = generate_roof(subdivided, params)
                self.assertEqual(differences(reference, snapshot(result)), [])
                assert_provenance(self, result, subdivided)


if __name__ == "__main__":
    unittest.main()
