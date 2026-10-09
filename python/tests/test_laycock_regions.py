# SPDX-License-Identifier: GPL-3.0-or-later
"""Diagnostic subdivision compatibility, not a roof appearance oracle."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from laycock_regions import cell_compatibility, difference, elementary, maximal_rectangles, priority_orders
from roof_generator.core.footprint import analyze
from shapely.geometry import box


class RegionProofs(unittest.TestCase):
    def test_reflex_subdivision_preserves_the_staggered_outline(self):
        fp=analyze(((0,0),(6,0),(6,3),(8,3),(8,6),(1,6),(1,3),(0,3)))
        atoms,rays=elementary(fp)
        self.assertEqual(len(atoms),4)
        self.assertAlmostEqual(sum(a.area for a in atoms)*fp.frame.scale**2,39)
        self.assertEqual(len(rays),4)

    def test_a_region_cannot_claim_a_whole_cell_from_a_partial_overlap(self):
        d=SimpleNamespace(vertices=((0,0),(4,0),(4,1),(0,1)),
                          cells=(SimpleNamespace(id=0,corners=(0,1,2,3)),))
        rows=cell_compatibility([box(0,0,2,1),box(2,0,4,1)],[(0,),(1,)],d)
        self.assertTrue(rows[0]['requires_split'])
        self.assertEqual(rows[0]['common_collections'],[])

    def test_elementary_rectangles_can_cross_minimum_cell_boundaries(self):
        d=SimpleNamespace(vertices=((0,0),(2,0),(4,0),(4,1),(2,1),(0,1)),
            cells=(SimpleNamespace(id=0,corners=(0,1,4,5)),SimpleNamespace(id=1,corners=(1,2,3,4))))
        rows=cell_compatibility([box(0,0,4,1)],[(0,)],d)
        self.assertEqual([r['intersection_areas'] for r in rows],[[2],[2]])
        self.assertEqual([r['atoms_crossing_cell_boundary'] for r in rows],[[0],[0]])
        self.assertFalse(any(r['requires_split'] for r in rows))

    def test_overlapping_collections_are_not_confluent_without_priority(self):
        groups=((0,1,2),(1,2,3))
        a=difference(groups,(0,1)); b=difference(groups,(1,0))
        self.assertEqual([r['atoms'] for r in a],[[0,1,2],[3]])
        self.assertEqual([r['atoms'] for r in b],[[1,2,3],[0]])

    def test_rectangle_growth_probe_has_one_maximal_rectangle(self):
        self.assertEqual(maximal_rectangles(((0,0),(4,0),(4,2),(0,2))),[(0,0,4,2)])

    def test_reflex_ray_intersection_uses_exact_boundary_coordinates(self):
        fp=analyze(((0,0),(108,0),(108,65),(162,65),(162,128),(204,128),
                    (204,177),(60,177),(60,121),(0,121)))
        atoms,_=elementary(fp)
        self.assertEqual(len(atoms),10)

    def test_all_priority_orders_expose_both_whole_cell_and_split_options(self):
        d=SimpleNamespace(vertices=((0,0),(4,0),(4,1),(0,1)),
                          cells=(SimpleNamespace(id=0,corners=(0,1,2,3)),))
        groups=((0,1),(0,),(1,))
        rows=cell_compatibility([box(0,0,2,1),box(2,0,4,1)],groups,d)
        result=priority_orders(groups,[rows],True)
        self.assertTrue(result['complete'])
        self.assertGreater(result['exact_configurations'],0)
        self.assertGreater(result['splitting_configurations'],0)
        self.assertFalse(priority_orders(groups,[rows],False)['complete'])


if __name__=='__main__':
    unittest.main()
