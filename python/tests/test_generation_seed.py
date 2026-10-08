# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math
from pathlib import Path
import subprocess
import sys
import python
import unittest
from roof_generator.core.seed import derive, choose, point_identity
from roof_generator.core.footprint import analyze


class GenerationSeedProof(unittest.TestCase):
    def test_namespace_order_and_unrelated_decisions_are_independent(self):
        items = ("axis-x", "axis-y", "receiver-b")
        result = choose(items, 123, "roof_candidate", key=lambda x: x)
        derive(123, "material", "face-a")
        self.assertEqual(
            result, choose(items[::-1], 123, "roof_candidate", key=lambda x: x)
        )
        self.assertGreater(
            len(
                {choose(items, s, "roof_candidate", key=lambda x: x) for s in range(40)}
            ),
            1,
        )
        with self.assertRaises(ValueError):
            choose(("same", "same"), 0, "roof_candidate", key=lambda x: x)

    def test_cross_process_seed_digest_does_not_use_python_hash(self):
        root = Path(__file__).resolve().parents[2]
        script = "import sys;sys.path.insert(0,sys.argv[1]+'/addon');from roof_generator.core.seed import derive;print(derive(-17,'square_axis','part-a'))"
        for _ in range(2):
            r = subprocess.run(
                [sys.executable, "-I", "-c", script, str(root)],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(r.stdout.strip(), derive(-17, "square_axis", "part-a"))

    def test_physical_identity_transforms_with_declared_direction(self):
        points = ((0, 0), (8, 0), (8, 4), (0, 4))
        expected = sorted(
            point_identity(analyze(points))(p) for p in analyze(points).vertices
        )
        angle = 0.729
        c, s = math.cos(angle), math.sin(angle)
        rotated = tuple((c * x - s * y + 31, s * x + c * y - 48) for x, y in points)
        for raw, direction in (
            (points[::-1], (1, 0)),
            (points[2:] + points[:2], (1, 0)),
            (rotated, (c, s)),
        ):
            fp = analyze(raw)
            self.assertEqual(
                expected, sorted(point_identity(fp, direction)(p) for p in fp.vertices)
            )
        with self.assertRaises(ValueError):
            point_identity(analyze(points), (0, 0))


if __name__ == "__main__":
    unittest.main()
