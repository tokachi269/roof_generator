# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent six-slope witnesses for simultaneous distinct-end replacements."""

from collections import Counter
from dataclasses import replace
import math
import json
from pathlib import Path
import python
import unittest

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from roof_generator.core.footprint import analyze
from roof_generator.core.partition_candidates import candidates
from roof_generator.core.architecture_selection import recommend
from roof_generator.core.topology_candidates import build_candidates
from python.tests.architecture_setup import compose
from roof_generator.core.mesh import RoofMesh
from roof_generator.core.solve import problem
from python.inspect_architectural_parts import fixture


def cycle(loop):
    return min(tuple(loop[i:] + loop[:i]) for i in range(len(loop)))


def witness(host_width, left_width, right_width):
    """Authored eave planes, not the generator's topology/initializer helpers."""
    w, h, l, r, end = 24.0, host_width, left_width, right_width, 16.0
    points = dict(
        A=(0, 0, 0),
        B=(w, 0, 0),
        C=(w, end, 0),
        D=(w - r, end, 0),
        E=(w - r, h, 0),
        F=(l, h, 0),
        G=(l, end, 0),
        H=(0, end, 0),
        PL=(l / 2, end, l / 4),
        PR=(w - r / 2, end, r / 4),
    )
    points.update(
        LH=(max(h, l) / 2, max(h, l) / 2, max(h, l) / 4),
        LL=(
            l / 2 if l <= h else l - h / 2,
            h - l / 2 if l <= h else h / 2,
            min(h, l) / 4,
        ),
        RH=(w - max(h, r) / 2, max(h, r) / 2, max(h, r) / 4),
        RL=(
            w - r / 2 if r <= h else w - r + h / 2,
            h - r / 2 if r <= h else h / 2,
            min(h, r) / 4,
        ),
    )
    faces = [
        ["D", "E", "RL"] + ([] if r <= h else ["RH"]) + ["PR"],
        ([] if r > h else ["RL"]) + ["RH", "B", "C", "PR"],
        ["E", "F", "LL"]
        + ([] if l > h else ["LH"])
        + ([] if r > h else ["RH"])
        + ["RL"],
        ["A", "B", "RH"]
        + ([] if r <= h else ["RL"])
        + ([] if l <= h else ["LL"])
        + ["LH"],
        ["H", "A", "LH"] + ([] if l > h else ["LL"]) + ["PL"],
        ([] if l <= h else ["LH"]) + ["LL", "F", "G", "PL"],
    ]
    # At equal width the two named joints denote one junction, not a short edge.
    aliases = {"LL": "LH"} if l == h else {}
    aliases.update({"RL": "RH"} if r == h else {})
    for face in faces:
        face[:] = [aliases.get(v, v) for v in face]
        face[:] = [v for i, v in enumerate(face) if v != face[i - 1]]
    for v in aliases:
        del points[v]
    raw = tuple(points[v][:2] for v in "ABCDEFGH")
    return raw, points, faces


def selected(raw, direction=(1, 0)):
    pool = build_candidates(
        recommend(candidates(analyze(raw))), reference_direction=direction
    )
    return pool, pool.select(13)


class TerminalNetworkProof(unittest.TestCase):
    def test_existing_candidate_family_and_seed_choices_match_frozen_reference(self):
        reference = json.loads(
            (
                Path(__file__).parent / "fixtures/seed_topology_reference.json"
            ).read_text()
        )
        for name, expected in reference["cases"].items():
            pool, _ = selected(fixture(name)["footprint"])
            original = tuple(c for c in pool.valid if c.id in expected["valid"])
            self.assertEqual(sorted(c.id for c in original), expected["valid"])
            added = tuple(c for c in pool.valid if c.id not in expected["valid"])
            for candidate in added:
                self.assertEqual(len(candidate.ends.joints), 1)
                self.assertEqual(candidate.ends.joints[0].kind, "extension")
                self.assertEqual(len(candidate.architecture.parts), 2)
                self.assertIn(len(candidate.graph.faces), (4, 5))
                if len(candidate.graph.faces) == 5:
                    internal = [f for f in candidate.graph.faces if not f.eaves]
                    self.assertEqual(len(internal), 1)
                    self.assertIsNotNone(internal[0].support)
                self.assertFalse(any(e.kind == "hip" for e in candidate.graph.edges))
            # Keep the old seed contract on the unchanged candidate family.
            # Adding a researched roof option deliberately expands that family.
            frozen_pool = replace(pool, valid=original)
            self.assertEqual(
                {str(s): frozen_pool.select(s).id for s in range(16)}, expected["choices"]
            )

    def test_original_U_is_one_graph_with_internal_receiver_ridge(self):
        pool, candidate = selected(fixture("orthogonal_U")["footprint"])
        graph = candidate.graph
        self.assertEqual(len(pool.valid), 1)
        self.assertEqual(len(candidate.architecture.parts), 1)
        self.assertEqual(len(graph.faces), 6)
        self.assertEqual(len(candidate.composition.connections), 2)
        self.assertEqual(
            Counter(e.kind for e in graph.edges if len(e.faces) == 2),
            {"ridge": 3, "valley": 2, "hip": 4},
        )
        self.assertEqual(
            sum(
                e.kind == "ridge"
                and all(graph.vertices[v].boundary is None for v in e.vertices)
                for e in graph.edges
            ),
            1,
        )
        interior_ridge = next(
            e
            for e in graph.edges
            if e.kind == "ridge"
            and all(graph.vertices[v].boundary is None for v in e.vertices)
        )
        fixed = dict(candidate.geometry.fixed_z)
        for v in interior_ridge.vertices:
            self.assertAlmostEqual(
                fixed[v] * candidate.architecture.decomposition.footprint.frame.scale,
                0.5 * 5.2 / 2,
                places=8,
            )
            self.assertNotIn(v, candidate.geometry.variable_z)
            self.assertIn(v, candidate.geometry.variable_xy)
        self.assertEqual(len(graph.vertices) - len(graph.edges) + len(graph.faces), 1)
        self.assertEqual({i for f in graph.faces for i in f.cells}, {0, 1, 2})
        self.assertEqual(
            {i for e in graph.edges if e.boundary for i in e.boundary.original_edges},
            set(range(8)),
        )

    def test_independent_planar_witnesses_cover_local_width_orderings(self):
        # Both narrower, both wider, equal, and one wider/one narrower.
        for dimensions in ((6, 4, 4), (4, 6, 6), (4, 4, 4), (6, 4, 8), (6, 5, 3)):
            with self.subTest(widths=dimensions):
                raw, points, faces = witness(*dimensions)
                pool, candidate = selected(raw)
                graph, d = candidate.graph, candidate.architecture.decomposition
                polygons = []
                for f in faces:
                    xyz = np.array([points[v] for v in f])
                    self.assertLess(
                        np.linalg.svd(xyz - xyz.mean(0), compute_uv=False)[-1], 1e-9
                    )
                    polygons.append(Polygon(xyz[:, :2]))
                self.assertLess(
                    unary_union(polygons).symmetric_difference(Polygon(raw)).area, 1e-9
                )
                self.assertLess(sum(p.area for p in polygons) - Polygon(raw).area, 1e-9)
                labels = {}
                for i, v in enumerate(graph.vertices):
                    if v.boundary is not None:
                        xy = d.footprint.frame.world_xy(v.seed)
                        labels[i] = next(
                            k for k, p in points.items() if math.dist(p[:2], xy) < 1e-7
                        )
                for i, v in enumerate(graph.vertices):
                    if v.boundary is None:
                        # Hip to an exterior corner identifies the higher joint;
                        # valley to a reflex corner identifies the lower joint.
                        neighbors = {
                            labels[u]: e.kind
                            for e in graph.edges
                            if i in e.vertices
                            for u in e.vertices
                            if u != i and u in labels
                        }
                        if neighbors.get("A") == "hip":
                            labels[i] = "LH"
                        elif neighbors.get("B") == "hip":
                            labels[i] = "RH"
                        elif neighbors.get("F") == "valley":
                            labels[i] = "LL"
                        elif neighbors.get("E") == "valley":
                            labels[i] = "RL"
                        else:
                            self.fail("unrecognized joint incidence")
                self.assertEqual(set(labels.values()), set(points))
                self.assertEqual(
                    {cycle([labels[i] for i in f.loop]) for f in graph.faces},
                    {cycle(f) for f in faces},
                )
                normalized = []
                frame = d.footprint.frame
                ux, uy = frame.direction
                for i in range(len(graph.vertices)):
                    x, y, z = points[labels[i]]
                    dx, dy = x - frame.origin[0], y - frame.origin[1]
                    normalized.append(
                        (
                            (dx * ux + dy * uy) / frame.scale,
                            (-dx * uy + dy * ux) / frame.scale,
                            z / frame.scale,
                        )
                    )
                RoofMesh(graph, tuple(normalized))
                geometry = problem(graph)
                for i, z in geometry.fixed_z:
                    self.assertAlmostEqual(z, normalized[i][2], places=8)
                for edge, direction in geometry.ridge_directions:
                    a, b = (normalized[v] for v in edge)
                    self.assertAlmostEqual(
                        (b[0] - a[0]) * direction[1] - (b[1] - a[1]) * direction[0],
                        0,
                        places=8,
                    )
                self.assertTrue(
                    all(
                        v.boundary is None
                        for v in graph.vertices
                        if v.role == "junction"
                    )
                )

    def test_distinct_end_replacements_also_work_on_opposite_receiver_sides(self):
        raw = ((0, -10), (4, -10), (4, 0), (24, 0), (24, 16), (20, 16), (20, 6), (0, 6))
        pool, candidate = selected(raw)
        graph = candidate.graph
        self.assertEqual(len(graph.faces), 6)
        connections = candidate.composition.connections
        self.assertEqual(len(connections), 2)
        self.assertEqual(len({c.host for c in connections}), 1)
        self.assertEqual(len({c.terminated_ports[0] for c in connections}), 2)
        self.assertEqual(
            Counter(e.kind for e in graph.edges if len(e.faces) == 2),
            {"ridge": 3, "valley": 2, "hip": 4},
        )
        # The same operation is selected without classifying the polygon shape.
        self.assertEqual(len(pool.valid), 1)

    def test_seed_and_incidence_are_stable_under_transforms_and_relation_order(self):
        raw = tuple(tuple(p) for p in fixture("orthogonal_U")["footprint"])
        expected, c = selected(raw)
        angle = 0.437
        co, si = math.cos(angle), math.sin(angle)
        middle = tuple((raw[0][k] + raw[1][k]) / 2 for k in (0, 1))
        for ring, direction in (
            (raw[::-1], (1, 0)),
            (raw[3:] + raw[:3], (1, 0)),
            (raw[:1] + (middle,) + raw[1:], (1, 0)),
            (
                tuple((co * x - si * y + 51, si * x + co * y - 29) for x, y in raw),
                (co, si),
            ),
        ):
            actual, _ = selected(ring, direction)
            self.assertEqual(
                {v.id for v in expected.valid}, {v.id for v in actual.valid}
            )
            for seed in (0, 1, 17):
                self.assertEqual(expected.select(seed).id, actual.select(seed).id)
        d = c.architecture.decomposition
        self.assertEqual(
            compose(d, axes=c.axes).graph.inspect(),
            compose(
                replace(d, adjacency=d.adjacency[::-1]), axes=c.axes
            ).graph.inspect(),
        )


if __name__ == "__main__":
    unittest.main()
