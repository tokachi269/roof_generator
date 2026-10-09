# SPDX-License-Identifier: GPL-3.0-or-later
"""Hierarchical supports before global roof decisions; no fabricated junctions."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'addon'))
from roof_generator.core.footprint import analyze
from roof_generator.core.recursive_regions import recursive_regions
from roof_generator.core.receiver_regions import receiver_regions
from roof_generator.core.member_layout import member_layout


def ancestry(node):
    edges={tuple(sorted((node.region,child.region))) for child in node.children}
    for child in node.children:edges.update(ancestry(child))
    return edges


class RecursiveRegionProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records=json.loads((Path(__file__).parent/'fixtures/user_roof_images_v1.json').read_text())['inputs']

    def test_nonrectangular_residuals_are_decomposed_recursively(self):
        fp=analyze(self.records[0]['footprint'])
        self.assertFalse(receiver_regions(fp).proposals)
        result=recursive_regions(fp)
        self.assertTrue(result.complete)
        self.assertTrue(result.proposals)
        self.assertGreaterEqual(max(tree.depth for identity,tree in result.structures),3)
        self.assertTrue(all(p.source=='recursive_regions' for p in result.proposals))

    def test_every_tree_owns_each_actual_region_exactly_once(self):
        for record in self.records:
            result=recursive_regions(analyze(record['footprint']))
            self.assertTrue(result.complete)
            proposals={p.id:p for p in result.proposals}
            for identity,tree in result.structures:
                self.assertEqual(sorted(tree.members()),list(range(len(proposals[identity].regions))))
                self.assertFalse(hasattr(tree,'boundary'))

    def test_distinct_ancestry_does_not_multiply_geometry_identity(self):
        result=recursive_regions(analyze(self.records[2]['footprint']))
        self.assertGreater(len(result.structures),len(result.proposals))
        self.assertEqual(len({p.id for p in result.proposals}),len(result.proposals))

    def test_real_contacts_are_not_replaced_by_ancestry(self):
        result=recursive_regions(analyze(self.records[2]['footprint']))
        proposals={p.id:p for p in result.proposals}
        # A residual can touch an ancestor through several descendants. A tree
        # is decomposition history, not a license to erase these cross-links.
        self.assertTrue(any({a.members for a in member_layout(proposals[i]).adjacency}
                            !=ancestry(tree) for i,tree in result.structures))

    def test_budget_exhaustion_is_explicit(self):
        fp=analyze(self.records[0]['footprint'])
        for kwargs in ({'max_work':1},{'max_candidates':1}):
            result=recursive_regions(fp,**kwargs)
            self.assertFalse(result.complete)
            self.assertTrue(result.reason)
            self.assertFalse(result.proposals)
            self.assertFalse(result.structures)

    def test_input_order_does_not_choose_an_owner(self):
        raw=self.records[2]['footprint']
        first=recursive_regions(analyze(raw));second=recursive_regions(analyze(list(reversed(raw))))
        self.assertEqual(first.structures,second.structures)
        self.assertEqual([p.id for p in first.proposals],[p.id for p in second.proposals])

    def test_noninteger_supports_bind_through_shared_boundary_authority(self):
        fp=analyze(((0,0),(.37,0),(.37,1.059),(0,1.059)))
        result=recursive_regions(fp)
        self.assertTrue(result.complete)
        self.assertEqual(len(result.structures),1)
        self.assertEqual(result.structures[0][1].members(),(0,))


if __name__=='__main__':unittest.main()
