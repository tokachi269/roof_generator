# SPDX-License-Identifier: GPL-3.0-or-later
"""Declared exterior semantics must survive the global topology boundary."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from itertools import combinations, product

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'addon'))
from python.roof_intent import (RoofIntent, IntentError, topology, cap_domain,
                               gable_configurations, subtract_domain)
from python.tests.test_whole_polygon_roofs import rectangle_skeleton
from roof_generator.core.footprint import analyze
from roof_generator.core.roof_regions import propose_regions
from roof_generator.core.member_layout import member_layout
from roof_generator.core import graph
from roof_generator.core.provenance import BoundaryPoint
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.core.solve import problem, solve


class BoundaryIntent(unittest.TestCase):
    def model(self, outline, regions=None, axes=(0,), source='declared'):
        fp = analyze(outline)
        regions = regions or (outline,)
        layout = member_layout(propose_regions(fp, regions, source=source))
        return fp, RoofIntent.declare(layout, axes)

    def test_square_has_two_axis_intents_without_cell_junctions(self):
        outline = [(0,0),(10,0),(10,10),(0,10)]
        fp, first = self.model(outline)
        _, second = self.model(outline, axes=(1,))
        points = list(fp.vertices)+[tuple((fp.vertices[0][k]+fp.vertices[2][k])/2 for k in (0,1))]
        skeleton = SimpleNamespace(
            nodes=[SimpleNamespace(position=SimpleNamespace(x=x*fp.frame.scale,y=y*fp.frame.scale))
                   for x,y in points],
            get_faces=lambda: [[i,(i+1)%4,4,i] for i in range(4)])
        for intent in (first, second):
            roof, _ = topology(intent, fp, skeleton, graph, BoundaryPoint, UnsupportedRoofError)
            mesh = solve(roof, problem(roof))
            self.assertIs(mesh.graph, roof)
            intent.verify(roof)
            self.assertEqual(len(roof.faces), 2)
            self.assertEqual(sum(e.kind == 'hip' for e in roof.edges), 0)
        self.assertNotEqual(first.caps(range(4)).selected, second.caps(range(4)).selected)

    def test_unavailable_transverse_gables_are_not_replaced_by_short_ends(self):
        fp, intent = self.model([(0,0),(10,0),(10,4),(0,4)], axes=(0,))
        skeleton = rectangle_skeleton(
            [(x*fp.frame.scale,y*fp.frame.scale) for x,y in fp.vertices], [])
        with self.assertRaisesRegex(IntentError, 'not an ordinary terminal cap'):
            topology(intent, fp, skeleton, graph, BoundaryPoint, UnsupportedRoofError)

    def test_partial_exterior_end_is_not_promoted_to_whole_edge(self):
        outline = [(0,0),(6,0),(6,3),(8,3),(8,6),(1,6),(1,3),(0,3)]
        regions = ([(1,0),(6,0),(6,6),(1,6)],
                   [(0,0),(1,0),(1,3),(0,3)],
                   [(6,3),(8,3),(8,6),(6,6)])
        fp, intent = self.model(outline, regions, (0,1,0))
        # Canonical region order is left leaf, central receiver, right leaf.
        choice = intent.caps(range(len(fp.vertices)))
        self.assertTrue(any(reason == 'mixed eave/gable intervals' for edge,reason in choice.gaps))
        self.assertEqual({i.edge for i in intent.intervals}, set(range(len(fp.vertices))))

    def test_source_name_cannot_change_end_authority(self):
        outline = [(0,0),(10,0),(10,4),(0,4)]
        _, first = self.model(outline, axes=(1,), source='minimum')
        _, second = self.model(outline, axes=(1,), source='receiver')
        self.assertEqual(first.intervals, second.intervals)
        self.assertEqual(first.caps(range(4)), second.caps(range(4)))
        fp, _ = self.model(outline)
        source = rectangle_skeleton([(x*fp.frame.scale,y*fp.frame.scale) for x,y in fp.vertices], [])
        roof,_ = topology(first, fp, source, graph, BoundaryPoint, UnsupportedRoofError)
        _, opposite = self.model(outline, axes=(0,))
        with self.assertRaisesRegex(IntentError, 'contradicts'):
            opposite.verify(roof)

    def test_mixed_model_declares_retained_hip_instead_of_ignoring_a_gable_request(self):
        outline = [(0,0),(10,0),(10,4),(0,4)]
        fp = analyze(outline)
        layout = member_layout(propose_regions(fp,(outline,),source='declared'))
        source = rectangle_skeleton([(x*fp.frame.scale,y*fp.frame.scale) for x,y in fp.vertices], [])
        available = [f[0] for f in source.get_faces() if len(f)==4]
        intent = RoofIntent.from_caps(layout,(1,),available[:1])
        roof,_ = topology(intent,fp,source,graph,BoundaryPoint,UnsupportedRoofError)
        intent.verify(roof)
        self.assertEqual(sum(e.kind=='hip' for e in roof.edges),2)
        with self.assertRaisesRegex(IntentError,'eave side'):
            RoofIntent.from_caps(layout,(0,),available[:1])

    def test_disconnected_exposures_of_one_end_cannot_take_different_shapes(self):
        outline = [(0,0),(4,0),(4,2),(8,2),(8,4),(4,4),(4,6),(8,6),(8,8),(0,8)]
        regions = ([(0,0),(4,0),(4,8),(0,8)],
                   [(4,2),(8,2),(8,4),(4,4)],[(4,6),(8,6),(8,8),(4,8)])
        fp = analyze(outline)
        layout = member_layout(propose_regions(fp,regions,source='declared'))
        member,side = next((m,s) for m in layout.supports for s in m.sides if len(s.exterior)>1)
        a,b = (layout.vertices[i] for i in side.vertices)
        axes = [0]*len(layout.supports)
        axes[member.id] = 1 if abs(a[0]-b[0])>abs(a[1]-b[1]) else 0
        with self.assertRaisesRegex(IntentError,'inconsistent exposed states'):
            RoofIntent.from_caps(layout,axes,(side.exterior[0].edge,))

    def test_factored_domains_equal_exhaustive_axis_and_end_choices(self):
        outline = [(0,0),(6,0),(6,3),(8,3),(8,6),(1,6),(1,3),(0,3)]
        regions = ([(1,0),(6,0),(6,6),(1,6)],
                   [(0,0),(1,0),(1,3),(0,3)],[(6,3),(8,3),(8,6),(6,6)])
        fp = analyze(outline)
        layout = member_layout(propose_regions(fp,regions,source='declared'))
        for size in range(1,len(fp.vertices)+1):
            for selected in combinations(range(len(fp.vertices)),size):
                mixed = []; pure = []
                for axes in product((0,1),repeat=len(layout.supports)):
                    try:
                        RoofIntent.from_caps(layout,axes,selected)
                        mixed.append(axes)
                    except IntentError: pass
                    choice = RoofIntent.declare(layout,axes).caps(range(len(fp.vertices)))
                    if not choice.gaps and choice.selected==selected: pure.append(axes)
                self.assertEqual(set(product(*RoofIntent.axis_domains(layout,selected))),set(mixed))
                self.assertEqual(set(product(*RoofIntent.axis_domains(layout,selected,'gable'))),set(pure))

    def test_maximal_ends_preserve_both_square_directions_and_do_not_select_single_hips(self):
        outline=[(0,0),(10,0),(10,10),(0,10)]
        fp=analyze(outline);layout=member_layout(propose_regions(fp,(outline,),source='declared'))
        points=list(fp.vertices)+[tuple((fp.vertices[0][k]+fp.vertices[2][k])/2 for k in (0,1))]
        skeleton=SimpleNamespace(
            nodes=[SimpleNamespace(position=SimpleNamespace(x=x*fp.frame.scale,y=y*fp.frame.scale)) for x,y in points],
            get_faces=lambda:[[i,(i+1)%4,4,i] for i in range(4)])
        available,conflicts,blocked=cap_domain(fp,skeleton)
        self.assertEqual(set(conflicts),{(0,1),(1,2),(2,3),(0,3)})
        pool=gable_configurations(layout,available,conflicts,blocked)
        self.assertTrue(pool.complete)
        self.assertEqual({c.selected for c in pool.configurations},{(0,2),(1,3)})
        for config in pool.configurations:
            for axes in product(*config.axis_domains):
                intent=RoofIntent.from_caps(layout,axes,config.selected)
                roof,_=topology(intent,fp,skeleton,graph,BoundaryPoint,UnsupportedRoofError)
                self.assertIs(solve(roof,problem(roof)).graph,roof)
        self.assertFalse(gable_configurations(layout,available,conflicts,blocked,max_work=1).complete)
        self.assertEqual(gable_configurations(layout,available,conflicts,blocked,max_work=1).configurations,())

    def test_dominance_matches_exhaustive_per_axis_order_without_area_priority(self):
        outline=[(0,0),(6,0),(6,3),(8,3),(8,6),(1,6),(1,3),(0,3)]
        regions=([(1,0),(6,0),(6,6),(1,6)],[(0,0),(1,0),(1,3),(0,3)],[(6,3),(8,3),(8,6),(6,6)])
        fp=analyze(outline);layout=member_layout(propose_regions(fp,regions,source='declared'))
        available=tuple(range(len(fp.vertices)));conflicts=((0,1),(2,3))
        expected=set()
        for axes in product((0,1),repeat=len(layout.supports)):
            feasible=[]
            for size in range(1,len(available)+1):
                for selected in combinations(available,size):
                    if any(a in selected and b in selected for a,b in conflicts):continue
                    try:RoofIntent.from_caps(layout,axes,selected)
                    except IntentError:continue
                    feasible.append(selected)
            expected.update((s,axes) for s in feasible if not any(set(s)<set(t) for t in feasible))
        pool=gable_configurations(layout,available,conflicts,max_work=1000000)
        self.assertTrue(pool.complete)
        actual={(c.selected,axes) for c in pool.configurations for axes in product(*c.axis_domains)}
        self.assertEqual(actual,expected)
        cube=((0,1),(0,1),(0,1));removed=((0,),(0,1),(1,))
        parts=subtract_domain(cube,removed)
        self.assertEqual({a for part in parts for a in product(*part)},set(product(*cube))-set(product(*removed)))


if __name__ == '__main__':
    unittest.main()
