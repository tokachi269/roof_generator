# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent planar source coverage and physical output transport proofs."""

import python
from dataclasses import replace
import math
import unittest
from roof_generator.mesh_input import generate_footprint_mesh
from roof_generator.core.generation import GenerationSettings
from roof_generator.core.errors import UnsupportedRoofError


class MeshAdapterProof(unittest.TestCase):
    def test_triangle_source_and_ngon_source_have_the_same_final_mesh(self):
        vertices = ((0, 0, 0), (12, 0, 0), (12, 6, 0), (0, 6, 0))
        for kind in ("gable", "hip", "shed", "flat"):
            settings = GenerationSettings(kind)
            a = generate_footprint_mesh(
                vertices, ((0, 1, 2), (0, 2, 3)), settings, reference_hint=(1, 0, 0)
            )
            b = generate_footprint_mesh(
                vertices, ((3, 2, 1, 0),), settings, reference_hint=(1, 0, 0)
            )
            self.assertEqual(a.spec, b.spec)
            self.assertEqual(
                a.roof.generation.selected.id, b.roof.generation.selected.id
            )

    def test_translation_tilt_and_nonuniform_scale_transport(self):
        c, s = math.cos(0.51), math.sin(0.51)

        def transform(p):
            x, y, z = p
            return (x + 120, c * y - s * z - 43, s * y + c * z + 18)

        points = ((0, 0, 0), (18, 0, 0), (18, 4, 0), (0, 4, 0))
        normal = (0, -s, c)
        result = generate_footprint_mesh(
            tuple(map(transform, points)),
            ((0, 1, 2, 3),),
            GenerationSettings("gable", eave_height=2),
            normal_hint=normal,
            reference_hint=(1, 0, 0),
            mesh_origin=(120, -43, 18),
        )
        self.assertEqual(result.spec.location, (120, -43, 18))
        for local in result.spec.vertices:
            x = local[0]
            y = c * local[1] + s * local[2]
            z = -s * local[1] + c * local[2]
            self.assertAlmostEqual(z, 2 + 0.5 * min(y, 4 - y), places=7)
            self.assertGreaterEqual(x, -1e-7)
            self.assertLessEqual(x, 18 + 1e-7)

    def test_core_absorbs_only_bounded_float32_transform_noise(self):
        from roof_generator.core.footprint import analyze, EPS

        raw = ((0, 0), (0.125, 0), (0.125 + 4.8e-9, 0.375), (4.8e-9, 0.375))
        fp = analyze(raw)
        self.assertTrue(fp.orthogonal)
        for point in fp.vertices:
            world = fp.frame.world_xy(point)
            self.assertLessEqual(
                min(math.dist(world, p) for p in raw), 4 * EPS * fp.frame.scale
            )
        skew = ((0, 0), (12, 0), (12.001, 6), (0.001, 6))
        self.assertFalse(analyze(skew).orthogonal)
        with self.assertRaises(UnsupportedRoofError):
            generate_footprint_mesh(tuple((*p, 0) for p in skew), ((0, 1, 2, 3),))

    def test_invalid_source_meshes_fail_without_topology_repair(self):
        v = ((0, 0, 0), (8, 0, 0), (8, 4, 0), (0, 4, 0))
        for faces in (
            (),
            ((0, 1, 2), (0, 1, 2)),
            ((0, 1, 2),),
            ((0, 1, 2), (0, 3, 2)),
            ((0, 1, 999),),
        ):
            with self.subTest(faces=faces), self.assertRaises(UnsupportedRoofError):
                generate_footprint_mesh(v, faces)
        with self.assertRaises(UnsupportedRoofError):
            generate_footprint_mesh(v[:3] + ((0, 4, 0.1),), ((0, 1, 2, 3),))
        with self.assertRaises(UnsupportedRoofError):
            generate_footprint_mesh(v, ((0, 1, 2, 3),), normal_hint=(1, 0, 0))


if __name__ == "__main__":
    unittest.main()
