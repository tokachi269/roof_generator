# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent incidence witness for the isolated published gable adjustment."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'addon'))
from python.whole_polygon_roofs import topology
from roof_generator.core import graph
from roof_generator.core.footprint import analyze
from roof_generator.core.provenance import BoundaryPoint
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.core.solve import problem,solve


def rectangle_skeleton(exterior,holes,subdivide=False):
    a,b,c,d=exterior
    width,height=b[0]-a[0],c[1]-a[1]
    if width>=height:
        y=(a[1]+c[1])/2
        radius=height/2
        points=[a,b,c,d,(a[0]+radius,y),(b[0]-radius,y)]
        faces=[[0,1,5,4,0],[1,2,5,1],[2,3,4,5,2],[3,0,4,3]]
    else:
        x=(a[0]+c[0])/2
        radius=width/2
        points=[a,b,c,d,(x,a[1]+radius),(x,c[1]-radius)]
        faces=[[0,1,4,0],[1,2,5,4,1],[2,3,5,2],[3,0,4,5,3]]
    if subdivide:
        points.append(tuple((points[4][k]+points[5][k])/2 for k in (0,1)))
        faces=[sum(([v,6] if {v,face[(j+1)%(len(face)-1)]}=={4,5}
                    else [v] for j,v in enumerate(face[:-1])),[])+[face[0]] for face in faces]
    return SimpleNamespace(nodes=[SimpleNamespace(position=SimpleNamespace(x=x,y=y)) for x,y in points],
                           get_faces=lambda:faces)


class WholePolygonWitness(unittest.TestCase):
    def test_explicit_opposite_caps_can_share_square_event(self):
        fp=analyze([(0,0),(10,0),(10,10),(0,10)])
        def square(exterior,holes):
            points=list(exterior)+[tuple((exterior[0][k]+exterior[2][k])/2 for k in (0,1))]
            return SimpleNamespace(nodes=[SimpleNamespace(position=SimpleNamespace(x=x,y=y)) for x,y in points],
                                   get_faces=lambda:[[i,(i+1)%4,4,i] for i in range(4)])
        with self.assertRaisesRegex(UnsupportedRoofError,'simultaneous terminal caps'):
            topology(fp,square,graph,BoundaryPoint,UnsupportedRoofError)
        roof,_=topology(fp,square,graph,BoundaryPoint,UnsupportedRoofError,selected_caps=(0,2))
        mesh=solve(roof,problem(roof))
        self.assertIs(mesh.graph,roof)
        self.assertEqual(len(roof.faces),2)
        self.assertEqual(sum(e.kind=='ridge' for e in roof.edges),1)
        self.assertEqual(sum(e.kind=='hip' for e in roof.edges),0)
        self.assertEqual(sum(v.boundary is None for v in roof.vertices),0)
        with self.assertRaisesRegex(UnsupportedRoofError,'uniquely incident slope sectors'):
            topology(fp,square,graph,BoundaryPoint,UnsupportedRoofError,selected_caps=(0,1))

    def test_explicit_single_end_preserves_the_other_hip_support(self):
        fp=analyze([(0,0),(10,0),(10,4),(0,4)])
        source=rectangle_skeleton(exterior=[(x*fp.frame.scale,y*fp.frame.scale) for x,y in fp.vertices],holes=[])
        caps=[face[0] for face in source.get_faces() if len(face)==4]
        roof,decisions=topology(fp,rectangle_skeleton,graph,BoundaryPoint,UnsupportedRoofError,selected_caps=(caps[0],))
        mesh=solve(roof,problem(roof))
        self.assertIs(mesh.graph,roof)
        self.assertEqual(decisions['cap_edges'],[caps[0]])
        self.assertEqual(len(roof.faces),3)
        self.assertTrue(any(f.support==caps[1] for f in roof.faces))
        self.assertEqual(sum(e.kind=='hip' for e in roof.edges),2)

    def test_gable_adjustment_consumes_terminal_faces_before_fixed_solve(self):
        fp=analyze([(0,0),(10,0),(10,4),(0,4)])
        roof,decisions=topology(fp,rectangle_skeleton,graph,BoundaryPoint,UnsupportedRoofError)
        self.assertEqual(len(roof.faces),2)
        self.assertEqual(sorted(e.kind for e in roof.edges),['eave','eave','gable_end','gable_end','gable_end','gable_end','ridge'])
        self.assertEqual(len(decisions['cap_edges']),2)
        mesh=solve(roof,problem(roof))
        self.assertIs(mesh.graph,roof)
        self.assertEqual(mesh.faces,tuple(f.loop for f in roof.faces))
        self.assertTrue(all(mesh.vertices[i][2]>0 for i,v in enumerate(roof.vertices) if v.role=='ridge_end'))

    def test_redundant_interior_crease_subdivision_does_not_become_junction(self):
        fp=analyze([(0,0),(10,0),(10,4),(0,4)])
        source=lambda exterior,holes:rectangle_skeleton(exterior,holes,subdivide=True)
        roof,_=topology(fp,source,graph,BoundaryPoint,UnsupportedRoofError)
        self.assertEqual(sum(e.kind=='ridge' for e in roof.edges),1)
        self.assertEqual(len(roof.vertices),6)
        self.assertEqual(sum(v.boundary is None for v in roof.vertices),0)

    def test_shared_event_keeps_third_slope_while_boundary_cap_is_separate(self):
        # A measured four-facet event, represented without the external
        # library. The old midpoint relocation cannot satisfy support 7.
        fp=analyze([(0,9),(6,9),(6,0),(12,0),(12,12),
                    (6,12),(6,18),(3,18),(3,15),(0,15)])
        extra=[(-.025,.025),(-.075,.075),(-.025,.075),(-.025,-.025),
               (0,.05),(-.1,.2),(-.1,.1)]
        loops=[[0,1,14,10],[1,2,14],[2,3,11,12,14],[3,4,15,16,11],
               [4,5,15],[5,6,16,15],[6,7,12,11,16],[7,8,13,10,14,12],
               [8,9,13],[9,0,10,13]]
        def source(exterior,holes):
            points=list(exterior)+[(x*fp.frame.scale,y*fp.frame.scale) for x,y in extra]
            return SimpleNamespace(
                nodes=[SimpleNamespace(position=SimpleNamespace(x=x,y=y)) for x,y in points],
                get_faces=lambda:[f+[f[0]] for f in loops])
        roof,_=topology(fp,source,graph,BoundaryPoint,UnsupportedRoofError)
        event=next(i for i,v in enumerate(roof.vertices) if v.seed==(0,.05))
        end=next(i for i,v in enumerate(roof.vertices) if v.boundary==BoundaryPoint(1,.5))
        self.assertNotEqual(event,end)
        self.assertIsNone(roof.vertices[event].boundary)
        self.assertEqual({f.support for f in roof.faces if event in f.loop},{0,2,7})
        self.assertEqual({f.support for f in roof.faces if end in f.loop},{0,2})
        mesh=solve(roof,problem(roof))
        self.assertIs(mesh.graph,roof)
        self.assertAlmostEqual(mesh.vertices[event][2],mesh.vertices[end][2])


if __name__=='__main__':unittest.main()
