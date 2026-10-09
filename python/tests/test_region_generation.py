# SPDX-License-Identifier: GPL-3.0-or-later
"""Polygon support must cross Cells before topology, without solver edits."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'addon'))
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.core.footprint import analyze
from roof_generator.core.generation import GenerationSettings
from roof_generator.core.partition_candidates import candidates
from roof_generator.core.region_generation import generate_region_roof, region_candidates
from roof_generator.core.roof_regions import propose_regions, minimum_regions


OUTLINE=((0,0),(6,0),(6,3),(8,3),(8,6),(1,6),(1,3),(0,3))
REGIONS=(((0,0),(1,0),(1,3),(0,3)),((1,0),(6,0),(6,6),(1,6)),
         ((6,3),(8,3),(8,6),(6,6)))


class RegionGenerationProof(unittest.TestCase):
    def test_central_support_crosses_original_cells_and_consumes_both_ends(self):
        fp=analyze(OUTLINE)
        d=candidates(fp).candidates[0]
        proposal=propose_regions(fp,REGIONS,source='explicit',provenance=d)
        roof=generate_region_roof((minimum_regions(d),proposal))
        selected=roof.generation.selected
        self.assertEqual(selected.axes,(0,1,0))
        self.assertEqual(selected.architecture.layout.candidate.id,proposal.id)
        self.assertEqual(len(proposal.regions[1].provenance),2)
        self.assertEqual(tuple(j.kind for j in selected.ends.joints),('shared','shared'))
        self.assertEqual(selected.architecture.parts[0].members,(0,1,2))
        self.assertEqual(roof.mesh.graph,selected.graph)
        self.assertEqual(selected.geometry.faces,tuple(f.loop for f in selected.graph.faces))
        self.assertEqual(len(roof.mesh.faces),6)
        self.assertIsNone(selected.recommendation.score)
        # Valleys remain where the shared L models require them, but no entire
        # internal valley is the zero-height seam between independent roofs.
        for edge in selected.graph.edges:
            if edge.kind=='valley':
                self.assertGreater(max(roof.mesh.vertices[v][2] for v in edge.vertices),0)
        self.assertTrue(all(feature.parts==(0,) for feature in selected.composition.features))

    def test_source_order_does_not_select_a_different_roof(self):
        fp=analyze(OUTLINE)
        a=propose_regions(fp,REGIONS,source='a')
        b=propose_regions(fp,tuple(tuple(reversed(r)) for r in reversed(REGIONS)),source='b')
        first=generate_region_roof((a,b),GenerationSettings(seed=43))
        second=generate_region_roof((b,a),GenerationSettings(seed=43))
        self.assertEqual(first.generation.selected.id,second.generation.selected.id)
        self.assertEqual(first.mesh,second.mesh)

    def test_unfinished_search_has_no_seed_winner(self):
        fp=analyze(OUTLINE)
        proposal=propose_regions(fp,REGIONS,source='explicit')
        pool=region_candidates((proposal,),GenerationSettings(max_axis_assignments=1))
        self.assertFalse(pool.complete)
        with self.assertRaises(UnsupportedRoofError):pool.select(0)

    def test_forged_end_configuration_is_rejected(self):
        proposal=propose_regions(analyze(OUTLINE),REGIONS,source='explicit')
        candidate=generate_region_roof((proposal,)).generation.selected
        with self.assertRaises(UnsupportedRoofError):
            replace(candidate,axes=(1,1,1))


if __name__=='__main__':unittest.main()
