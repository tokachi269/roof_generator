# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent incidence, height, projection and counterexample proofs."""
from dataclasses import asdict
import itertools
import math
import unittest
from unittest.mock import patch
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from python.roof_kernel_proof import (
    BoundaryPath, Line, RoofIntent, ProofBudget, ProofDomainError,
    construct, from_record, nonexistence_witness,
)


def build(points,roles):
    return from_record({'footprint':points,'roles':roles})


def independent(test,result):
    xy=np.asarray([v.xy for v in result.vertices])
    time=np.asarray([v.time for v in result.vertices])
    coords=np.asarray(result.coordinates(pitch=.73,eave_height=2.4))
    outline=np.asarray(result.boundary.outline)
    original=Polygon(outline)
    patches=[]
    forward=original.exterior.is_ccw
    distances=[]
    roles=dict(result.intent.roles)
    for source in result.boundary.sources:
        if roles[source.id]!='EAVE':continue
        direction=np.asarray(source.end)-np.asarray(source.start)
        normal=np.array([-direction[1],direction[0]])/np.linalg.norm(direction)
        if not forward:normal=-normal
        distances.append((xy-np.asarray(source.start))@normal)
    np.testing.assert_allclose(time,np.min(distances,axis=0),atol=1e-8)
    test.assertGreaterEqual(float(time.min()),-1e-9)
    for face in result.patches:
        ring=xy[list(face.loop)]; xyz=coords[list(face.loop)]
        shape=Polygon(ring)
        test.assertTrue(shape.is_valid);test.assertGreater(shape.area,1e-10)
        test.assertTrue(shape.exterior.is_ccw)
        test.assertLess(np.linalg.svd(xyz-xyz.mean(axis=0),compute_uv=False)[-1],1e-8)
        test.assertGreater(np.cross(xyz[1]-xyz[0],xyz[2]-xyz[0])[2],0.)
        patches.append(shape)
    test.assertLess(unary_union(patches).symmetric_difference(original).area,1e-8)
    test.assertLess(abs(sum(s.area for s in patches)-original.area),1e-8)
    for a,b in itertools.combinations(patches,2):test.assertLess(a.intersection(b).area,1e-9)
    for event in result.events:
        for contact in event.contacts:
            vertex=result.vertices[contact.vertex]
            test.assertAlmostEqual(vertex.time,event.time,places=8)
            test.assertGreaterEqual(len(contact.sources),3)


class BoundaryKernelProof(unittest.TestCase):
    def test_nonparallel_gable_is_declared_before_construction(self):
        points=((0,0),(9,0),(11,3),(8,7),(1,6))
        path,intent=build(points,('EAVE','GABLE','EAVE','GABLE','GABLE'))
        with (patch('roof_generator.core.wavefront.compute_skeleton',side_effect=AssertionError('ordinary SS')),
              patch('roof_generator.core.solve.solve',side_effect=AssertionError('embedding'))):
            result=construct(path,intent)
        independent(self,result)
        self.assertEqual({p.source for p in result.patches},{'edge0','edge2'})
        self.assertEqual(len(result.patches),2)
        self.assertTrue(any(v.time>0 for v in result.vertices))

    def test_exhaustive_full_edge_roles_on_convex_proof_domain(self):
        # Every nonempty eave subset, including adjacent gable runs, not just
        # pairs recognizable as terminal triangular ordinary-skeleton caps.
        count=0
        for n in range(3,9):
            points=tuple((8*math.cos(2*math.pi*i/n+.13),5*math.sin(2*math.pi*i/n+.13)) for i in range(n))
            for bits in range(1,1<<n):
                roles=tuple('EAVE' if bits&(1<<i) else 'GABLE' for i in range(n))
                with self.subTest(n=n,bits=bits):
                    result=construct(*build(points,roles));independent(self,result)
                count+=1
        self.assertEqual(count,498)

    def test_same_time_cluster_retains_all_contacts_and_supports(self):
        square=((0,0),(8,0),(8,8),(0,8))
        result=construct(*build(square,('EAVE',)*4))
        independent(self,result)
        self.assertEqual(len(result.events),1)
        self.assertEqual(len(result.events[0].contacts),1)
        self.assertEqual(len(result.events[0].contacts[0].sources),4)
        rectangle=((0,0),(12,0),(12,6),(0,6))
        result=construct(*build(rectangle,('EAVE',)*4))
        independent(self,result)
        self.assertEqual(len(result.events),1)
        self.assertEqual(len(result.events[0].contacts),2)
        self.assertAlmostEqual(result.events[0].time,3.)
        gable=construct(*build(rectangle,('EAVE','GABLE','EAVE','GABLE')))
        independent(self,gable)
        self.assertEqual(len(gable.patches),2)
        self.assertEqual(len(gable.events[0].contacts),2)

    def test_source_identity_and_physical_roof_survive_transforms(self):
        path,intent=build(((0,0),(9,0),(11,3),(8,7),(1,6)),('EAVE','GABLE','EAVE','GABLE','GABLE'))
        result=construct(path,intent)
        base=sorted((tuple(np.round(v.xy,8)),round(v.time,8),v.sources) for v in result.vertices)
        rotated=BoundaryPath(path.sources[2:]+path.sources[:2])
        reversed_path=BoundaryPath(tuple(Line(s.id,s.end,s.start) for s in reversed(path.sources)))
        for variant in (rotated,reversed_path):
            actual=construct(variant,intent);independent(self,actual)
            signature=sorted((tuple(np.round(v.xy,8)),round(v.time,8),v.sources) for v in actual.vertices)
            self.assertEqual(signature,base)
        angle=.73
        rotation=np.array(((math.cos(angle),-math.sin(angle)),(math.sin(angle),math.cos(angle))))
        translation=np.array((91.2,-48.7))
        def transform(p):return tuple(rotation@np.asarray(p)+translation)
        moved=BoundaryPath(tuple(Line(s.id,transform(s.start),transform(s.end)) for s in path.sources))
        actual=construct(moved,intent);independent(self,actual)
        restored=sorted((tuple(np.round(rotation.T@(np.asarray(v.xy)-translation),8)),round(v.time,8),v.sources)
                        for v in actual.vertices)
        self.assertEqual(restored,base)
        self.assertEqual(asdict(construct(path,intent)),asdict(result))

    def test_single_eave_on_concave_side_has_a_nonexistence_certificate(self):
        points=((0,0),(8,0),(8,3),(3,3),(3,8),(0,8))
        path,intent=build(points,('GABLE','GABLE','GABLE','EAVE','GABLE','GABLE'))
        witness=nonexistence_witness(path,intent,(6,1))
        self.assertIsNotNone(witness)
        self.assertAlmostEqual(witness['inward_distances']['edge3'],-3.)
        # Necessary success is not converted into an admissibility certificate.
        self.assertIsNone(nonexistence_witness(path,intent,(1,6)))
        with self.assertRaises(ProofDomainError):construct(path,intent)

    def test_budget_and_undefined_transition_do_not_publish_a_prefix(self):
        path,intent=build(((0,0),(8,0),(8,8),(0,8)),('EAVE',)*4)
        with self.assertRaises(ProofBudget):construct(path,intent,max_work=1)
        path,intent=build(((0,0),(4,0),(8,0),(8,8),(0,8)),('EAVE','GABLE','EAVE','EAVE','EAVE'))
        with self.assertRaisesRegex(ProofDomainError,'collinear'):construct(path,intent)
        path,_=build(((0,0),(8,0),(8,8),(0,8)),('EAVE',)*4)
        for roles in ((('edge0','EAVE'),),tuple((s.id,'GABLE') for s in path.sources)):
            with self.assertRaises(ValueError):construct(path,RoofIntent(roles))


if __name__=='__main__':unittest.main()
