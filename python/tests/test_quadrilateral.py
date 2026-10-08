# SPDX-License-Identifier: GPL-3.0-or-later
import python
import gzip
import json
import math
from pathlib import Path
import unittest
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from roof_generator.core.generation import (
    generate_roof,
    prepare_generation,
    GenerationSettings,
)
from roof_generator.core.errors import UnsupportedRoofError


class QuadProof(unittest.TestCase):
    def check(self, raw, seed):
        r = generate_roof(raw, GenerationSettings(seed=seed, eave_height=2))
        self.assertEqual(len(r.mesh.faces), 2)
        self.assertEqual(len(r.generation.candidates.valid), 2)
        d = r.generation.selected.architecture.decomposition
        self.assertIsNone(d.certificate)
        self.assertEqual((len(d.cells), len(d.adjacency)), (1, 0))
        self.assertFalse(r.generation.selected.architecture.members[0].axes)
        self.assertEqual(
            len(r.generation.selected.architecture.members[0].directions), 2
        )
        vertices = np.asarray(
            [r.generation.footprint.frame.world_xyz(p) for p in r.mesh.vertices]
        )
        outline = np.asarray(
            [r.generation.footprint.frame.world_xy(p) for p in r.mesh.graph.outline]
        )
        polys = []
        for face in r.mesh.graph.faces:
            xyz = vertices[list(face.loop)]
            self.assertLess(
                np.linalg.svd(xyz - xyz.mean(axis=0), compute_uv=False)[-1], 1e-7
            )
            e = face.eaves[0]
            a, b = outline[e], outline[(e + 1) % 4]
            v = b - a
            normal = np.array([-v[1], v[0]]) / np.linalg.norm(v)
            np.testing.assert_allclose(
                xyz[:, 2], 2 + 0.5 * ((xyz[:, :2] - a) @ normal), atol=1e-7
            )
            polys.append(Polygon(xyz[:, :2]))
        self.assertLess(
            unary_union(polys).symmetric_difference(Polygon(raw)).area, 1e-8
        )
        self.assertLess(abs(sum(p.area for p in polys) - Polygon(raw).area), 1e-8)
        return r

    def test_all_frozen_convex_quad_probes_are_real_solved_meshes(self):
        path = Path(__file__).parents[1] / "docs/canonical/coverage_inputs_v1.json.gz"
        records = json.loads(gzip.decompress(path.read_bytes()))["corpora"][
            "convex_quadrilateral"
        ]
        for r in records:
            with self.subTest(case=r["name"]):
                self.check(r["footprint"], 7)

    def test_seeds_choose_both_geometric_eave_directions_without_index_dependence(self):
        raw = np.array([(0, 0), (13.8, 0), (11.7, 7.4), (1.2, 7.4)])
        ids = {
            prepare_generation(raw, GenerationSettings(seed=i)).selected.id
            for i in range(20)
        }
        self.assertEqual(len(ids), 2)
        angle = 0.483
        rot = np.array(
            [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
        )
        base = self.check(raw, 7)
        expected = sorted(
            tuple(np.round(base.generation.footprint.frame.world_xyz(p), 6))
            for p in base.mesh.vertices
        )
        for variant in (
            raw[::-1],
            np.roll(raw, 2, axis=0),
            np.array(
                [
                    p
                    for a, b in zip(raw, np.roll(raw, -1, axis=0))
                    for p in (a, (a + b) / 2)
                ]
            ),
        ):
            r = generate_roof(
                variant @ rot.T + [43, -21],
                GenerationSettings(
                    seed=7, eave_height=2, reference_direction=tuple(rot @ [1, 0])
                ),
            )
            actual = [
                r.generation.footprint.frame.world_xyz(p) for p in r.mesh.vertices
            ]
            actual = sorted(
                tuple(np.round((*((np.array(p[:2]) - [43, -21]) @ rot), p[2]), 6))
                for p in actual
            )
            self.assertEqual(actual, expected)

    def test_shed_flat_share_cell_contract_and_hip_has_explicit_scope(self):
        raw = [(0, 0), (13.8, 0), (11.7, 7.4), (1.2, 7.4)]
        for kind in ("shed", "flat"):
            r = generate_roof(raw, GenerationSettings(kind))
            self.assertEqual(len(r.mesh.faces), 1)
        with self.assertRaisesRegex(UnsupportedRoofError, "nonrectangular primitive"):
            prepare_generation(raw, GenerationSettings("hip"))
