# SPDX-License-Identifier: GPL-3.0-or-later
"""Indexed member geometry must come from actual roof supports, never Cells."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'addon'))
from roof_generator.core.footprint import analyze
from roof_generator.core.roof_regions import propose_regions
from roof_generator.core.member_layout import member_layout


class MemberLayoutContract(unittest.TestCase):
    def test_central_region_publishes_two_attachment_contacts(self):
        fp=analyze(((0,0),(6,0),(6,3),(8,3),(8,6),(1,6),(1,3),(0,3)))
        outlines=(((0,0),(1,0),(1,3),(0,3)),
                  ((1,0),(6,0),(6,6),(1,6)),
                  ((6,3),(8,3),(8,6),(6,6)))
        proposal=propose_regions(fp,outlines,source='explicit-central')
        layout=member_layout(proposal)
        self.assertEqual(len(layout.supports),3)
        self.assertEqual({a.members for a in layout.adjacency},{(0,1),(1,2)})
        self.assertEqual(layout.candidate,proposal)
        self.assertEqual(layout.vertices[:len(fp.vertices)],fp.vertices)
        for support,region in zip(layout.supports,proposal.regions):
            self.assertEqual(tuple(layout.vertices[i] for i in support.corners),region.boundary)


if __name__=='__main__':unittest.main()
