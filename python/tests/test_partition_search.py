# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "addon"))
from roof_generator.core.roof_geometry import (
    normalize_footprint, UnsupportedRoofError, properties,
)
from roof_generator.core.roof_parts import _candidate_cuts, decompose, RoofParameters
from shapely.ops import split
import numpy as np


class PartitionSearchTests(unittest.TestCase):
    def test_convex_leaf_only_computes_rich_properties_for_partition_cost(self):
        footprint = normalize_footprint([(0, 0), (17, 0), (17, 9), (0, 9)])
        with patch(
            "roof_generator.core.roof_parts.properties", wraps=properties
        ) as observed:
            result = decompose(footprint)
        self.assertEqual(len(result.parts), 1)
        self.assertEqual(observed.call_count, 1)

    def test_pitch_and_eave_changes_reuse_partition_without_stale_parameters(self):
        footprint = normalize_footprint(
            [(0, 0), (13, 0), (13, 4), (5, 4), (5, 11), (0, 11)]
        )
        first = decompose(footprint, RoofParameters(pitch=0.4))
        changed = RoofParameters(pitch=0.7, eave_height=0.12)
        with patch(
            "roof_generator.core.roof_parts._candidate_cuts", wraps=_candidate_cuts
        ) as observed:
            second = decompose(footprint, changed)
        observed.assert_not_called()
        self.assertEqual(first.cuts, second.cuts)
        self.assertEqual(first.cost, second.cost)
        self.assertTrue(all(part.parameters == changed for part in second.parts))
        self.assertTrue(all(part.parameters.pitch == 0.4 for part in first.parts))

    def test_cached_hip_triangle_is_not_accepted_for_gable(self):
        footprint = normalize_footprint([(0, 0), (8, 0), (2, 6)])
        self.assertEqual(len(decompose(footprint, RoofParameters("hip")).parts), 1)
        with self.assertRaises(UnsupportedRoofError):
            decompose(footprint, RoofParameters("gable"))

    def test_same_polygon_with_subdivided_edges_retains_current_provenance(self):
        points = [(0, 0), (13, 0), (13, 4), (5, 4), (5, 11), (0, 11)]
        decompose(normalize_footprint(points))
        subdivided = []
        for a, b in zip(points, points[1:] + points[:1]):
            subdivided.extend([a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)])
        result = decompose(normalize_footprint(subdivided))
        originals = {
            i for part in result.parts for edge in part.source_edges
            for i in edge.original_edges
        }
        self.assertEqual(originals, set(range(len(subdivided))))

    def test_repeated_edge_directions_do_not_repeat_polygon_splits(self):
        cases = json.loads(
            (Path(__file__).parent / "fixtures/roof_acceptance.json").read_text()
        )
        case = next(c for c in cases if c["name"] == "orthogonal_L")
        footprint = normalize_footprint(case["footprint"])
        p = np.asarray(footprint.polygon.exterior.coords)[:-1]
        edges = np.roll(p, -1, axis=0) - p
        directions = edges / np.linalg.norm(edges, axis=1)[:, None]
        with patch("roof_generator.core.roof_parts.split", wraps=split) as observed:
            cuts = _candidate_cuts(footprint.polygon, directions)
        self.assertTrue(cuts)
        cutters = [call.args[1].wkb for call in observed.call_args_list]
        self.assertEqual(len(cutters), len(set(cutters)))

    def test_quad_search_does_not_emit_triangular_cut_pieces(self):
        footprint = normalize_footprint(
            [(0, 0), (13, 0), (13, 4), (5, 4), (5, 11), (0, 11)]
        )
        p = np.asarray(footprint.polygon.exterior.coords)[:-1]
        edges = np.roll(p, -1, axis=0) - p
        directions = edges / np.linalg.norm(edges, axis=1)[:, None]
        cuts = _candidate_cuts(
            footprint.polygon, directions, minimum_vertices=4,
        )
        self.assertTrue(cuts)
        for _, pieces in cuts:
            for piece in pieces:
                self.assertGreaterEqual(len(piece.exterior.coords) - 1, 4)
