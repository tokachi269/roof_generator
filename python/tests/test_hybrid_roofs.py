# SPDX-License-Identifier: GPL-3.0-or-later
"""Geometric contract of declared extension composition, without old templates."""
from fractions import Fraction as Q
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'addon'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hybrid_roofs import Architecture, HybridError, coordinates, topology, slopes, domains, patches, merge
from roof_generator.core.footprint import analyze
from roof_generator.core import graph as graph_api
from roof_generator.core.provenance import BoundaryPoint
from roof_generator.core.solve import problem, solve


def build(outline, boxes, axes):
    fp=analyze(outline);exact,_=coordinates(fp,outline)
    ux,uy=fp.frame.direction;origin=tuple(Q(str(x)) for x in fp.frame.origin);scale=Q(str(fp.frame.scale))
    def transform(p):
        x,y=(Q(str(p[k]))-origin[k] for k in (0,1))
        return ((x*Q(ux)+y*Q(uy))/scale,(-x*Q(uy)+y*Q(ux))/scale)
    rectangles=[]
    for a,b,c,d in boxes:
        ring=[transform(p) for p in ((a,b),(c,b),(c,d),(a,d))]
        rectangles.append((min(p[0] for p in ring),min(p[1] for p in ring),
                           max(p[0] for p in ring),max(p[1] for p in ring)))
    local_axes=tuple(a if uy==0 else 1-a for a in axes)
    architecture=Architecture.declare(tuple(rectangles),local_axes)
    graph,decisions=topology(fp,architecture,graph_api,BoundaryPoint,exact)
    mesh=solve(graph,problem(graph))
    return fp,architecture,graph,mesh


class HybridTests(unittest.TestCase):
    def test_narrow_branch_is_extended_to_receiver_without_internal_cap(self):
        _,_,graph,mesh=build([(0,0),(4,0),(4,-4),(8,-4),(8,0),(12,0),(12,6),(0,6)],
                             [(0,0,12,6),(4,-4,8,0)],(0,1))
        self.assertIs(mesh.graph,graph)
        self.assertEqual(sum(e.kind=='valley' for e in graph.edges),2)
        self.assertEqual(sum(e.kind=='hip' for e in graph.edges),0)
        for edge in graph.edges:
            if edge.kind=='gable_end':self.assertIsNotNone(edge.boundary)

    def test_opposite_equal_width_branches_share_one_simultaneous_ridge_event(self):
        _,_,graph,mesh=build([(0,0),(4,0),(4,-4),(8,-4),(8,0),(12,0),
                              (12,4),(8,4),(8,8),(4,8),(4,4),(0,4)],
                             [(0,0,12,4),(4,-4,8,0),(4,4,8,8)],(0,1,1))
        self.assertIs(mesh.graph,graph)
        self.assertEqual(sum(e.kind=='valley' for e in graph.edges),4)
        self.assertEqual(sum(e.kind=='ridge' for e in graph.edges),4)
        self.assertEqual(sum(v.role=='junction' for v in graph.vertices),1)

    def test_nested_branch_composition_preserves_connected_fixed_graph(self):
        outline=[(0,0),(4,0),(4,-2),(0,-2),(0,-6),(4,-6),(4,-8),
                 (8,-8),(8,0),(12,0),(12,6),(0,6)]
        _,_,graph,mesh=build(outline,[(0,0,12,6),(4,-8,8,0),(0,-6,4,-2)],(0,1,0))
        self.assertIs(mesh.graph,graph)
        self.assertEqual(sum(e.kind=='valley' for e in graph.edges),4)
        self.assertEqual(sum(e.kind=='hip' for e in graph.edges),0)

    def test_parallel_long_side_contact_is_not_a_declared_branch(self):
        with self.assertRaisesRegex(HybridError,'contact has no declared'):
            Architecture.declare(((Q(0),Q(0),Q(6),Q(3)),(Q(1),Q(3),Q(8),Q(6))),(0,0))

    def test_offset_end_profiles_fail_geometrically_instead_of_getting_a_seam(self):
        architecture=Architecture.declare(((Q(0),Q(0),Q(4),Q(4)),(Q(4),Q(1),Q(8),Q(5))),(0,0))
        with self.assertRaisesRegex(HybridError,'contact profiles are discontinuous'):
            patches(architecture)

    def test_branch_does_not_reappear_on_receivers_opposite_slope(self):
        architecture=Architecture.declare(((Q(0),Q(0),Q(12),Q(6)),(Q(4),Q(-4),Q(8),Q(0))),(0,1))
        planes,groups=domains(architecture)
        self.assertEqual(groups[0][1][1],(Q(4),Q(0),Q(8),Q(3)))
        for plane,ring,_ in merge(patches(architecture)):
            if plane in slopes(architecture.boxes[1],1):
                self.assertLessEqual(max(p[1] for p in ring),Q(2))

    def test_input_order_translation_scale_and_quarter_rotation_preserve_features(self):
        outline=[(0,0),(4,0),(4,-4),(8,-4),(8,0),(12,0),(12,6),(0,6)]
        boxes=[(0,0,12,6),(4,-4,8,0)]
        first=build(outline,boxes,(0,1))[2]
        transform=lambda p:(100-3*p[1],-20+3*p[0])
        altered=[transform(p) for p in reversed(outline[3:]+outline[:3])]
        moved=[]
        for a,b,c,d in boxes:
            corners=[transform(p) for p in ((a,b),(c,b),(c,d),(a,d))]
            moved.append((min(p[0] for p in corners),min(p[1] for p in corners),
                          max(p[0] for p in corners),max(p[1] for p in corners)))
        second=build(altered,moved,(1,0))[2]
        self.assertEqual(first.inspect()['features'],second.inspect()['features'])
        self.assertEqual(len(first.faces),len(second.faces))


if __name__=='__main__':unittest.main()
