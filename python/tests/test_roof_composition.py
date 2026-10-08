# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent published-attachment fixtures and pre-edit relation proofs."""

from collections import Counter
from dataclasses import replace
import math
from pathlib import Path
import json
import unittest

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from python.graph_first.footprint import analyze
from python.graph_first.cells import decompose
from python.graph_first.topology import _rectangle_graph, compose
from python.graph_first.connections import plan
from python.graph_first.graph import UnsupportedGraphError
from python.graph_first.geometry import Mesh, problem

RECORDS = json.loads(
    (Path(__file__).parent / "fixtures/rectangle_partition.json").read_text()
)
REFERENCES = json.loads(
    (Path(__file__).parent / "fixtures/roof_composition.json").read_text()
)


def cycle(loop):
    return min(tuple(loop[i:] + loop[:i]) for i in range(len(loop)))


def assert_reference(test, record, decomposition, graph, rotation=None, offset=None):
    """Literal face/edge oracle; no production compositor helper supplies answers."""
    rotation = np.eye(2) if rotation is None else rotation
    offset = np.zeros(2) if offset is None else offset
    points = record["points"]
    raw = {
        tuple(np.round(points[v][:2], 6)): v
        for v in record["outline"] + record["ports"]
    }
    labels = {}
    for i, vertex in enumerate(graph.vertices):
        if vertex.boundary is not None:
            xy = (
                np.array(decomposition.footprint.frame.world_xy(vertex.seed)) - offset
            ) @ rotation
            test.assertIn(tuple(np.round(xy, 6)), raw)
            labels[i] = raw[tuple(np.round(xy, 6))]
    expected_neighbors = {
        v: {next(u for u in edge if u != v) for edge in record["ridge"] if v in edge}
        for v in record["junctions"]
    }
    for i, vertex in enumerate(graph.vertices):
        if vertex.boundary is None:
            neighbors = {
                labels[u]
                for e in graph.edges
                if e.kind == "ridge" and i in e.vertices
                for u in e.vertices
                if u != i and u in labels
            }
            candidates = [
                v for v, adjacent in expected_neighbors.items() if adjacent == neighbors
            ]
            test.assertEqual(len(candidates), 1)
            labels[i] = candidates[0]
    test.assertEqual(set(labels.values()), set(points))
    expected = {
        tuple(sorted(edge)): kind
        for kind in ("ridge", "valley", "hip")
        for edge in record[kind]
    }
    counts = Counter(
        tuple(sorted((a, b)))
        for face in record["faces"]
        for a, b in zip(face, face[1:] + face[:1])
    )
    for edge, count in counts.items():
        if count == 1:
            expected[edge] = (
                "gable_end" if set(edge).intersection(record["ports"]) else "eave"
            )
    actual = {tuple(sorted(labels[i] for i in e.vertices)): e.kind for e in graph.edges}
    test.assertEqual(actual, expected)
    literal_faces = {
        cycle(f): owner for f, owner in zip(record["faces"], record["face_cells"])
    }
    cell_ids = {}
    for cell in decomposition.cells:
        xy = [
            tuple(
                np.round(
                    (
                        np.array(
                            decomposition.footprint.frame.world_xy(
                                decomposition.vertices[i]
                            )
                        )
                        - offset
                    )
                    @ rotation,
                    6,
                )
            )
            for i in cell.corners
        ]
        name = next(
            k
            for k, corners in record["cell_corners"].items()
            if set(xy) == {tuple(np.round(points[v][:2], 6)) for v in corners}
        )
        cell_ids[cell.id] = name
    test.assertEqual(
        {cycle([labels[i] for i in f.loop]): cell_ids[f.cells[0]] for f in graph.faces},
        literal_faces,
    )
    test.assertTrue(all(len(f.cells) == 1 for f in graph.faces))
    test.assertEqual(
        {i for f in graph.faces for i in f.cells}, {c.id for c in decomposition.cells}
    )
    for face_id, face in enumerate(graph.faces):
        owned = {
            e.boundary.edge
            for e in graph.edges
            if e.boundary and e.faces == (face_id,) and e.kind == "eave"
        }
        test.assertEqual(set(face.eaves), owned)
    # Artificial cuts cannot survive as a final edge, even under another name.
    for adjacency in decomposition.adjacency:
        cut = [decomposition.vertices[i] for i in adjacency.interval]
        test.assertFalse(
            any(
                {tuple(np.round(graph.vertices[i].seed, 9)) for i in e.vertices}
                == {tuple(np.round(p, 9)) for p in cut}
                for e in graph.edges
            )
        )
    # Independent planarity/coverage witness for these exact production cycles.
    normalized = []
    frame = decomposition.footprint.frame
    u = np.array(frame.direction)
    transform = np.array([[u[0], -u[1]], [u[1], u[0]]])
    for i in range(len(graph.vertices)):
        xyz = points[labels[i]]
        world = np.array(xyz[:2]) @ rotation.T + offset
        normalized.append(
            (*((world - frame.origin) @ transform / frame.scale), xyz[2] / frame.scale)
        )
    Mesh(graph, tuple(normalized))
    p = problem(graph, 0.5)
    test.assertEqual(
        set(p.variable_xy),
        {i for i, v in enumerate(graph.vertices) if v.boundary is None},
    )
    for i, height in p.fixed_z:
        test.assertAlmostEqual(height, normalized[i][2], places=8)
    for edge, direction in p.ridge_directions:
        a, b = (normalized[i] for i in edge)
        test.assertAlmostEqual(
            (b[0] - a[0]) * direction[1] - (b[1] - a[1]) * direction[0], 0, places=8
        )
    return labels


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


class MiddleCompositionTests(unittest.TestCase):
    def test_published_middle_cycles_replace_the_internal_branch_cap(self):
        for record in REFERENCES[:3]:
            with self.subTest(name=record["name"]):
                d = decompose(
                    analyze([record["points"][v][:2] for v in record["outline"]])
                )
                composition = compose(d)
                assert_reference(self, record, d, composition.graph)
                self.assertEqual(len(composition.connections), 1)
                self.assertEqual(composition.connections[0].kind, "middle")
                self.assertEqual(len(composition.connections[0].terminated_ports), 1)
                # The initializer is disposable and deliberately differs from
                # the independent exact common-pitch witness on narrow cases.
                if record is REFERENCES[0]:
                    joint = composition.connections[0].junctions[0]
                    exact = record["points"]["J"][:2]
                    self.assertGreater(
                        np.linalg.norm(
                            np.array(
                                d.footprint.frame.world_xy(
                                    composition.graph.vertices[joint].seed
                                )
                            )
                            - exact
                        ),
                        0.1,
                    )
                self.assertEqual(compose(d), composition)

    def test_middle_semantics_survive_input_metamorphisms(self):
        angle = 0.731
        rotation = np.array(
            [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
        )
        for record in REFERENCES[:3]:
            points = np.array([record["points"][v][:2] for v in record["outline"]])
            collinear = [
                p
                for a, b in zip(points, np.roll(points, -1, axis=0))
                for p in (a, (a + b) / 2)
            ]
            variants = [
                (points[::-1], np.eye(2), np.zeros(2)),
                (np.roll(points, 3, axis=0), np.eye(2), np.zeros(2)),
                (collinear, np.eye(2), np.zeros(2)),
                (points + [123, -456], np.eye(2), np.array([123, -456])),
                (points @ rotation.T + [20, -13], rotation, np.array([20, -13])),
            ]
            for outline, r, t in variants:
                with self.subTest(name=record["name"]):
                    d = decompose(analyze(outline))
                    graph = compose(d).graph
                    assert_reference(self, record, d, graph, r, t)
                    self.assertEqual(
                        {
                            i
                            for e in graph.edges
                            if e.boundary
                            for i in e.boundary.original_edges
                        },
                        set(range(len(outline))),
                    )

    def test_independent_oracle_rejects_lost_main_ridge_and_wrong_valley(self):
        record = REFERENCES[0]
        d = decompose(analyze([record["points"][v][:2] for v in record["outline"]]))
        graph = compose(d).graph
        for kind in ("ridge", "valley"):
            edge = next(e for e in graph.edges if e.kind == kind)
            broken = replace(
                graph,
                edges=tuple(
                    replace(e, kind="hip") if e == edge else e for e in graph.edges
                ),
            )
            with self.assertRaises(AssertionError):
                assert_reference(self, record, d, broken)


if __name__ == "__main__":
    unittest.main()
