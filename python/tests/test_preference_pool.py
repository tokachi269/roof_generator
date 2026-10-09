# SPDX-License-Identifier: GPL-3.0-or-later
"""A completed global pool is required before deterministic seed selection."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'addon'))
from python.probe_roof_preference import inspect
from roof_generator.core.receiver_regions import ReceiverRegions


def square(exterior,holes):
    points=list(exterior)+[tuple((exterior[0][k]+exterior[2][k])/2 for k in (0,1))]
    return SimpleNamespace(
        nodes=[SimpleNamespace(position=SimpleNamespace(x=x,y=y)) for x,y in points],
        get_faces=lambda:[[i,(i+1)%4,4,i] for i in range(4)])


class GlobalPool(unittest.TestCase):
    def test_external_face_extraction_failure_is_recorded_without_aborting_corpus(self):
        def failure(**kwargs):
            def get_faces():raise RuntimeError('external initiating-edge mismatch')
            return SimpleNamespace(get_faces=get_faces)
        with patch.dict(sys.modules,{'py_straight_skeleton':SimpleNamespace(compute_skeleton=failure)}):
            row=inspect(dict(name='square',footprint=[(0,0),(10,0),(10,10),(0,10)]),65536,0)
        self.assertEqual(row['stage'],'dependency')
        self.assertIn('initiating-edge mismatch',row['error'])
        self.assertFalse(row['embedded'])
        self.assertEqual(row.get('selectable_ids',[]),[])

    def test_incomplete_peer_source_prevents_seed_even_with_verified_minimum_roofs(self):
        with patch.dict(sys.modules,{'py_straight_skeleton':SimpleNamespace(compute_skeleton=square)}), \
             patch('roof_generator.core.receiver_regions.receiver_regions',
                   return_value=ReceiverRegions((),False,1,'source budget exhausted')):
            row=inspect(dict(name='square',footprint=[(0,0),(10,0),(10,10),(0,10)]),65536,0)
        self.assertTrue(row['existence_certified'])
        self.assertFalse(row['embedded'])
        self.assertFalse(row['search_complete'])
        self.assertEqual(row['selectable_ids'],[])
        self.assertNotIn('selected_id',row)

    def test_aliases_and_input_order_do_not_change_seed_or_multiply_probability(self):
        outline=[(0,0),(10,0),(10,10),(0,10)]
        variants=(outline,outline[2:]+outline[:2],list(reversed(outline)),
                  [(3*x+11,3*y-7) for x,y in outline])
        with patch.dict(sys.modules,{'py_straight_skeleton':SimpleNamespace(compute_skeleton=square)}):
            rows=[inspect(dict(name='square',footprint=ring),65536,42) for ring in variants]
            seeds={inspect(dict(name='square',footprint=outline),65536,i)['selected_id'] for i in range(8)}
        self.assertTrue(all(r['embedded'] and r['search_complete'] for r in rows))
        self.assertEqual(len(seeds),2)
        self.assertEqual(len({r['selected_id'] for r in rows}),1)
        self.assertTrue(all(len(r['choices'])==2 for r in rows))
        self.assertTrue(all(len(c['origins'])==2 for r in rows for c in r['choices']))
        self.assertEqual(len({tuple(sorted(r['selectable_ids'])) for r in rows}),1)


if __name__=='__main__':unittest.main()
