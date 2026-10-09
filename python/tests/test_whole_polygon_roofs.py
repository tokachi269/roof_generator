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
    y=(a[1]+c[1])/2
    radius=(c[1]-a[1])/2
    points=[a,b,c,d,(a[0]+radius,y),(b[0]-radius,y)]
    faces=[[0,1,5,4,0],[1,2,5,1],[2,3,4,5,2],[3,0,4,3]]
    if subdivide:
        points.append(((points[4][0]+points[5][0])/2,y))
        faces[0]=[0,1,5,6,4,0];faces[2]=[2,3,4,6,5,2]
    return SimpleNamespace(nodes=[SimpleNamespace(position=SimpleNamespace(x=x,y=y)) for x,y in points],
                           get_faces=lambda:faces)


class WholePolygonWitness(unittest.TestCase):
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


if __name__=='__main__':unittest.main()
