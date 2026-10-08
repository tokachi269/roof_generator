# SPDX-License-Identifier: GPL-3.0-or-later
"""Cache-free equivalence and broad-phase exclusion against unchanged predicates."""

import python
import unittest
from unittest.mock import patch
from roof_generator.core.footprint import analyze
from roof_generator.core.partition import complete_cuts, subdivide
from roof_generator.core.partition_candidates import candidates, signature
from python.inspect_architectural_parts import fixture


class PartitionReuseProof(unittest.TestCase):
    def test_clearing_boundary_hit_lookup_changes_no_completion(self):
        for name in ("orthogonal_U", "cross", "grid_14", "grid_20", "grid_40"):
            fp = analyze(fixture(name)["footprint"])
            search = candidates(fp)
            cache = {}
            for d in search.candidates:
                cert = d.certificate
                axes = tuple(
                    int(abs(c.end[1] - c.start[1]) > abs(c.end[0] - c.start[0]))
                    for c in cert.completions
                )
                expected = complete_cuts(fp, cert.selection, axes)
                self.assertEqual(
                    expected,
                    complete_cuts(fp, cert.selection, axes, boundary_hits=cache),
                )
                cache.clear()
                self.assertEqual(
                    expected,
                    complete_cuts(fp, cert.selection, axes, boundary_hits=cache),
                )

    def test_indexed_noding_matches_unfiltered_segment_predicates(self):
        for name in ("orthogonal_U", "cross", "grid_14", "grid_20", "grid_40"):
            fp = analyze(fixture(name)["footprint"])
            search = candidates(fp)
            for d in search.candidates:
                c = d.certificate
                indexed = subdivide(fp, c.selection, c.completions)
                # Disable only bounding-box exclusion. The independent full scan
                # applies on_segment to every node, exactly as specified.
                with patch(
                    "roof_generator.core.partition.bisect_left", return_value=0
                ), patch(
                    "roof_generator.core.partition.bisect_right",
                    side_effect=lambda index, *args: len(index),
                ):
                    unfiltered = subdivide(fp, c.selection, c.completions)
                self.assertEqual(indexed, unfiltered)


if __name__ == "__main__":
    unittest.main()
