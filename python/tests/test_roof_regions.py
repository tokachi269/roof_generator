# SPDX-License-Identifier: GPL-3.0-or-later
"""Region geometry authority, independent of roof validity and Cell ownership."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'addon'))
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.core.roof_regions import propose_regions, minimum_regions, parallel_recommendation


OUTLINE = ((0,0),(6,0),(6,3),(8,3),(8,6),(1,6),(1,3),(0,3))


def rectangle(a,b,c,d):
    return ((a,b),(c,b),(c,d),(a,d))


class RegionContract(unittest.TestCase):
    def setUp(self):
        self.fp = analyze(OUTLINE)
        self.d = decompose(self.fp)
        self.regions = (rectangle(1,0,6,6),rectangle(0,0,1,3),rectangle(6,3,8,6))

    def test_central_region_crosses_cells_without_changing_them(self):
        candidate = propose_regions(self.fp,self.regions,source='explicit-central',provenance=self.d)
        central = next(r for r in candidate.regions if len(r.provenance)==2)
        self.assertEqual(len(self.d.cells),2)
        self.assertAlmostEqual(central.area*self.fp.frame.scale**2,30)
        self.assertEqual(sorted(round(p.area*self.fp.frame.scale**2) for p in central.provenance),[15,15])
        self.assertFalse(hasattr(candidate,'valid_roof'))

    def test_sources_and_order_do_not_multiply_geometry_identity(self):
        a = propose_regions(self.fp,self.regions,source='A',provenance=self.d)
        b = propose_regions(self.fp,tuple(tuple(reversed(r)) for r in reversed(self.regions)),source='B')
        self.assertEqual(a.id,b.id)
        self.assertNotEqual(a.source,b.source)

    def test_minimum_proposals_use_the_same_contract(self):
        a = minimum_regions(self.d)
        b = propose_regions(self.fp,[tuple(self.fp.frame.world_xy(self.d.vertices[i]) for i in c.corners) for c in self.d.cells],source='other')
        self.assertEqual(a.id,b.id)
        self.assertEqual(len(a.regions),2)

    def test_missing_area_is_not_filled(self):
        with self.assertRaisesRegex(UnsupportedRoofError,'uncovered'):
            propose_regions(self.fp,self.regions[:2],source='missing')

    def test_narrow_gap_above_coordinate_allowance_is_rejected(self):
        regions=(rectangle(1,0,6-1e-5,6),self.regions[1],self.regions[2])
        with self.assertRaisesRegex(UnsupportedRoofError,'uncovered'):
            propose_regions(self.fp,regions,source='gap')

    def test_overlap_is_not_resolved_by_input_order(self):
        with self.assertRaisesRegex(UnsupportedRoofError,'overlap'):
            propose_regions(self.fp,(rectangle(0,0,6,3),rectangle(1,3,8,6),self.regions[0]),source='overlap')

    def test_exterior_area_is_rejected(self):
        with self.assertRaisesRegex(UnsupportedRoofError,'outside'):
            propose_regions(self.fp,(rectangle(0,0,8,6),),source='outside')

    def test_disconnected_collection_is_not_split(self):
        with self.assertRaises(UnsupportedRoofError):
            propose_regions(self.fp,((self.regions[1],self.regions[2]),self.regions[0]),source='disconnected')

    def test_self_touching_region_is_rejected(self):
        with self.assertRaises(UnsupportedRoofError):
            propose_regions(self.fp,(((0,0),(2,2),(0,2),(2,0)),),source='bowtie')

    def test_parallel_penalty_has_an_explicit_rectangle_model_domain(self):
        old = minimum_regions(self.d)
        recommendation = parallel_recommendation(old,(0,0))
        self.assertEqual(recommendation.score,-2)
        self.assertEqual(len(recommendation.parallel_contacts),1)
        central = propose_regions(self.fp,self.regions,source='central')
        # Transverse attachment axes are outside Hu's long-axis primitive domain.
        proposal = parallel_recommendation(central,(0,1,0))
        self.assertEqual(proposal.parallel_contacts,())
        self.assertIsNone(proposal.score)
        self.assertEqual(proposal.unscored_regions,(0,2))


if __name__ == '__main__':
    unittest.main()
