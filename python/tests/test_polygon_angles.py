# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual direction, incidence and independent plane/projection proofs."""
import python
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from roof_generator.core.footprint import analyze
from roof_generator.core.generation import generate_roof, GenerationSettings
from roof_generator.core.polygon_roof import PolygonRoof, topology
from roof_generator.core.wavefront import wavefront
from roof_generator.core.roof_intent import cap_domain
from roof_generator.core.solve import problem, solve
from roof_generator.core.errors import UnsupportedRoofError


def acceptance(name):
    rows=json.loads((Path(__file__).parent/'fixtures/roof_acceptance.json').read_text())
    return next(r['footprint'] for r in rows if r['name']==name)


def witness(test, graph, mesh, *, pitch=.5, eave=0.):
    """Independent plane distances, SVD, projection union and Euler incidence."""
    points=np.asarray(mesh.vertices)
    outline=np.asarray(graph.outline)
    projected=[]
    test.assertEqual(len(points)-len(graph.edges)+len(graph.faces),1)
    for face in graph.faces:
        xyz=points[list(face.loop)]
        origin=outline[face.support if face.support is not None else face.eaves[0]]
        support=face.support if face.support is not None else face.eaves[0]
        direction=outline[(support+1)%len(outline)]-origin
        inward=np.array([-direction[1],direction[0]])/np.linalg.norm(direction)
        np.testing.assert_allclose(xyz[:,2],eave+pitch*((xyz[:,:2]-origin)@inward),atol=1e-9)
        test.assertLess(np.linalg.svd(xyz-xyz.mean(axis=0),compute_uv=False)[-1],1e-9)
        projected.append(Polygon(xyz[:,:2]))
    test.assertLess(unary_union(projected).symmetric_difference(Polygon(outline)).area,1e-10)
    test.assertLess(abs(sum(p.area for p in projected)-Polygon(outline).area),1e-10)
    test.assertEqual(mesh.faces,tuple(f.loop for f in graph.faces))


class PolygonAngles(unittest.TestCase):
    def test_all_eave_hip_does_not_require_rectangles_or_parallel_supports(self):
        cases=[acceptance(n) for n in ('parallelogram','trapezoid','general_convex_quad','oblique_L')]
        cases.extend([[(0,0),(8,0),(2,6)],[(0,0),(10,0),(12,3),(8,7),(0,5)]])
        for raw in cases:
            with self.subTest(raw=raw), patch('roof_generator.core.generation.candidates',
                                             side_effect=AssertionError('rectangle partition')):
                result=generate_roof(raw,GenerationSettings('hip',pitch=.7,eave_height=2))
                generation=result.generation
                witness(self,result.mesh.graph,result.mesh,pitch=.7,eave=2/generation.footprint.frame.scale)
                self.assertEqual(generation.selected.architecture.gable_edges,())
                self.assertTrue(all(e.kind=='eave' for e in result.mesh.graph.edges if e.boundary))
                self.assertEqual(len(generation.candidates.valid),1)

    def test_square_polygon_junction_gets_its_height_from_planes(self):
        fp=analyze(((0,0),(10,0),(10,10),(0,10)))
        graph,_=topology(PolygonRoof(fp,(),'hip'),wavefront(fp))
        mesh=solve(graph,problem(graph))
        witness(self,graph,mesh)
        self.assertAlmostEqual(max(p[2] for p in mesh.vertices)*fp.frame.scale,2.5)
        self.assertEqual(len(graph.faces),4)
        self.assertEqual(sum(e.kind=='hip' for e in graph.edges),4)

    def test_terminal_disk_uses_opposed_supports_without_right_angles(self):
        for name in ('parallelogram','trapezoid','oblique_L'):
            fp=analyze(acceptance(name)); incidence=wavefront(fp)
            available,_,blocked=cap_domain(fp,incidence)
            ends=tuple(e for e in available if e not in blocked)
            graph,_=topology(PolygonRoof(fp,ends),incidence)
            mesh=solve(graph,problem(graph))
            witness(self,graph,mesh)
            self.assertTrue(ends)
            self.assertFalse(fp.orthogonal)
            self.assertEqual(sum(e.kind=='gable_end' for e in graph.edges),2*len(ends))

    def test_failed_event_never_retries_quad_or_changes_roof_type(self):
        with patch('roof_generator.core.wavefront.compute_skeleton',side_effect=RuntimeError('bad event')):
            with self.assertRaisesRegex(UnsupportedRoofError,'unresolved polygon roof event'):
                generate_roof(acceptance('trapezoid'),GenerationSettings('hip'))


if __name__=='__main__':unittest.main()
