# SPDX-License-Identifier: GPL-3.0-or-later
"""Global front incidence, source equations and independent polygon coverage."""
from collections import Counter
from fractions import Fraction as Q
import gzip
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from python.roof_kernel.boundary import BoundaryPath,Line,RoofIntent
from python.roof_kernel.wavefront import construct
from python.roof_kernel.admissibility import InconsistentIntent
from python.roof_kernel.complex import KernelLimit

ROOT=Path(__file__).resolve().parents[2]


def model(points,gables=()):
    points=tuple(tuple(p) for p in points)
    path=BoundaryPath(tuple(Line(f'edge{i}',a,b) for i,(a,b) in enumerate(zip(points,points[1:]+points[:1]))))
    intent=RoofIntent(tuple((s.id,'GABLE' if i in gables else 'EAVE') for i,s in enumerate(path.sources)))
    return path,intent


def witness(test,result):
    coords=np.asarray(result.coordinates(pitch=.73,eave_height=2.4))
    outlines=Polygon(np.asarray(result.boundary.outline,dtype=float))
    source={s.id:s for s in result.boundary.sources}
    role=dict(result.intent.roles);forward=outlines.exterior.is_ccw
    projected=[];incidence=Counter();used=set()
    for face in result.patches+result.walls:
        xyz=coords[list(face.loop)];used.update(face.loop)
        offsets=xyz-xyz[0]
        normal=sum((np.cross(a,b) for a,b in zip(offsets,np.roll(offsets,-1,axis=0))),np.zeros(3))
        test.assertGreater(np.linalg.norm(normal),1e-10)
        test.assertLess(np.linalg.svd(xyz-xyz.mean(axis=0),compute_uv=False)[-1],1e-8)
        for sid in face.sources:
            s=source[sid];a=np.asarray(s.start,dtype=float);b=np.asarray(s.end,dtype=float)
            n=np.array([-(b-a)[1],(b-a)[0]])/np.linalg.norm(b-a)
            if not forward:n=-n
            distance=(xyz[:,:2]-a)@n
            if role[sid]=='EAVE':np.testing.assert_allclose(xyz[:,2],2.4+.73*distance,atol=1e-8)
            else:np.testing.assert_allclose(distance,0,atol=1e-8)
        for a,b in zip(face.loop,face.loop[1:]+face.loop[:1]):incidence[tuple(sorted((a,b)))]+=1
        if face in result.patches:
            shape=Polygon(xyz[:,:2]);test.assertTrue(shape.is_valid);test.assertGreater(shape.area,1e-10)
            projected.append(shape)
    test.assertTrue(all(n in (1,2) for n in incidence.values()))
    test.assertEqual(len(used)-len(incidence)+len(result.patches)+len(result.walls),1)
    test.assertLess(unary_union(projected).symmetric_difference(outlines).area,1e-8)
    test.assertLess(abs(sum(p.area for p in projected)-outlines.area),1e-8)
    for event in result.events:
        time=result.precision.approximate(event.time)
        for v in event.contacts:test.assertAlmostEqual(result.precision.approximate(result.vertices[v].time),time,places=8)


class LineWavefront(unittest.TestCase):
    def test_concave_inputs_do_not_call_cap_solver_or_polygon_boolean(self):
        points=((0,0),(10,0),(10,3),(3,3),(3,9),(0,9))
        with (patch('roof_generator.core.wavefront.compute_skeleton',side_effect=AssertionError('ordinary skeleton')),
              patch('roof_generator.core.solve.solve',side_effect=AssertionError('embedding'))):
            result=construct(*model(points,(1,4)))
        witness(self,result)
        self.assertEqual({sid for p in result.patches for sid in p.sources},{'edge0','edge2','edge3','edge5'})
        self.assertEqual({sid for p in result.walls for sid in p.sources},{'edge1','edge4'})

    def test_same_cluster_handles_branches_without_shape_classes(self):
        cases=[
            (((0,0),(14,0),(14,4),(9,4),(9,12),(5,12),(5,4),(0,4)),(1,4,7)),
            (((0,0),(12,0),(12,10),(9,10),(9,4),(3,4),(3,10),(0,10)),(2,6)),
            (((0,4),(4,4),(4,0),(8,0),(8,4),(12,4),(12,8),(8,8),(8,12),(4,12),(4,8),(0,8)),(2,5,8,11)),
        ]
        for points,gables in cases:
            for ends in ((),gables):
                with self.subTest(points=points,ends=ends):
                    result=construct(*model(points,ends));witness(self,result)
                    self.assertTrue(result.events)

    def test_fixed_all_eave_acceptance_with_actual_angles(self):
        rows=json.loads((ROOT/'python/tests/fixtures/roof_acceptance.json').read_text())
        for row in rows:
            with self.subTest(name=row['name']):witness(self,construct(*model(row['footprint'])))

    def test_exact_rigid_transform_winding_and_cyclic_source_identity(self):
        path,intent=model(((0,0),(10,0),(10,3),(3,3),(3,9),(0,9)),(1,4))
        base=construct(path,intent)
        def signature(result):
            values=result.coordinates()
            return sorted((p.sources,tuple(sorted(tuple(round(x,8) for x in values[v]) for v in p.loop)))
                          for p in result.patches+result.walls)
        for transformed in (BoundaryPath(path.sources[3:]+path.sources[:3]),
                            BoundaryPath(tuple(Line(s.id,s.end,s.start) for s in reversed(path.sources)))):
            self.assertEqual(signature(base),signature(construct(transformed,intent)))
        def move(p):return Q(3,5)*p[0]-Q(4,5)*p[1]+77,Q(4,5)*p[0]+Q(3,5)*p[1]-41
        moved=BoundaryPath(tuple(Line(s.id,move(s.start),move(s.end)) for s in path.sources))
        actual=construct(moved,intent);witness(self,actual)
        self.assertEqual(len(actual.patches),len(base.patches));self.assertEqual(len(actual.events),len(base.events))
        for v in actual.vertices:
            x,y=map(actual.precision.approximate,v.xy)
            restored=(.6*(x-77)+.8*(y+41),-.8*(x-77)+.6*(y+41))
            time=actual.precision.approximate(v.time)
            self.assertTrue(any(np.linalg.norm(np.asarray(restored)-p[:2])<1e-8 and abs(time-(p[2]/.5))<1e-8
                                for p in base.coordinates()))

    def test_source_coverage_certificate_and_incomplete_execution_are_distinct(self):
        with self.assertRaises(InconsistentIntent) as error:
            construct(*model(((0,0),(8,0),(8,3),(3,3),(3,8),(0,8)),(0,1,2,4,5)))
        self.assertEqual(error.exception.certificate['kind'],'no_nonnegative_source_plane')
        with self.assertRaises(KernelLimit):construct(*model(((0,0),(8,0),(8,8),(0,8))),max_work=1)


if __name__=='__main__':unittest.main()
