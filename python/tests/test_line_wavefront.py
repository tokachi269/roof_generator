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
from python.roof_kernel.wavefront import construct,Wavefront
from python.roof_kernel.admissibility import InconsistentIntent
from python.roof_kernel.complex import KernelLimit
from python.roof_kernel.mesh import view,WallRequired,MeshResolutionError

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
    def test_boundary_and_role_containers_are_immutable_snapshots(self):
        points=[[0,0],[8,0],[8,4],[0,4]]
        sources=[Line(f'edge{i}',a,b) for i,(a,b) in enumerate(zip(points,points[1:]+points[:1]))]
        roles=[[s.id,'EAVE'] for s in sources]
        path=BoundaryPath(sources);intent=RoofIntent(roles)
        points[0][0]=999;sources.clear();roles[0][1]='GABLE'
        self.assertEqual(path.outline,((0,0),(8,0),(8,4),(0,4)))
        self.assertEqual(intent.roles[0],('edge0','EAVE'))
        witness(self,construct(path,intent))

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

    def test_stationary_remainder_is_a_scoped_model_certificate(self):
        points=((0,0),(8,0),(8,3),(3,3),(3,8),(0,8))
        # The right EAVE's plane 8-x is nonnegative everywhere. Passing that
        # necessary plane condition does not establish causal-front completion.
        self.assertTrue(all(8-x>=0 for x,y in points))
        wf=Wavefront(*model(points,(0,3,4,5)))
        with self.assertRaises(InconsistentIntent) as error:wf.run()
        certificate=error.exception.certificate
        self.assertEqual(certificate['kind'],'stationary_remaining_front')
        self.assertEqual(certificate['time'],3.)
        self.assertEqual(certificate['exact_time'],{'numerator':[('1','3')],'denominator':[('1','1')]})
        self.assertIn('not arbitrary source-plane roofs',certificate['scope'])
        self.assertEqual({tuple(map(Q,p)) for p in certificate['exact_polygons'][0]},
                         {(Q(0),Q(0)),(Q(3),Q(0)),(Q(3),Q(8)),(Q(0),Q(8))})

    def test_memos_are_not_correctness_dependencies(self):
        class NoMemo(Wavefront):
            def at(self,*args):
                self.registry.aliases.clear();self.precision.roots.clear()
                self.positions.clear();return super().at(*args)
            def contains(self,*args):
                self.intervals.clear();return super().contains(*args)
            def split(self,*args):
                self.subdivisions.clear();return super().split(*args)
        for points,ends in ((((0,0),(10,0),(10,3),(3,3),(3,9),(0,9)),(1,4)),
                            (((0,0),(8,2),(9,7),(1,5)),(1,3))):
            path,intent=model(points,ends)
            expected=construct(path,intent).inspect();actual=NoMemo(path,intent).run().inspect()
            for record in (expected,actual):record.pop('predicates')
            self.assertEqual(expected,actual)

    def test_collinear_source_subdivision_keeps_geometry_and_all_provenance(self):
        base=construct(*model(((0,0),(10,0),(10,3),(3,3),(3,9),(0,9)),(1,4)))
        split=construct(*model(((0,0),(4,0),(10,0),(10,3),(3,3),(3,9),(0,9)),(2,5)))
        witness(self,split)
        self.assertEqual(len(split.patches),len(base.patches))
        self.assertEqual(len(split.events),len(base.events))
        self.assertTrue(any({'edge0','edge1'}<=set(p.sources) for p in split.patches))
        def polygons(r):
            xyz=r.coordinates()
            return sorted(tuple(sorted(tuple(round(x,8) for x in xyz[v]) for v in p.loop)) for p in r.patches+r.walls)
        self.assertEqual(polygons(base),polygons(split))

    def test_all_full_edge_assignments_on_a_concave_polygon(self):
        p=((0,0),(8,0),(8,3),(3,3),(3,8),(0,8))
        valid=invalid=0
        for mask in range(1,64):
            gables=tuple(i for i in range(6) if not mask&(1<<i))
            try:result=construct(*model(p,gables))
            except InconsistentIntent as exc:
                self.assertTrue(exc.certificate);invalid+=1
            else:witness(self,result);valid+=1
        self.assertEqual((valid,invalid),(59,4))

    def test_simultaneous_contact_valence_and_actual_component_split(self):
        hexagon=((5,Q(5,2)),(0,Q(25,4)),(-5,Q(5,2)),(-5,-Q(5,2)),(0,-Q(25,4)),(5,-Q(5,2)))
        r=construct(*model(hexagon));witness(self,r)
        self.assertEqual(len(r.events),1)
        self.assertEqual([len(r.vertices[v].sources) for v in r.events[0].contacts],[6])
        rectangle=construct(*model(((0,0),(8,0),(8,4),(0,4))))
        self.assertEqual(len(rectangle.events),1)
        self.assertEqual(len(rectangle.events[0].contacts),2)
        neck=((0,0),(4,0),(4,2),(8,2),(8,0),(12,0),(12,6),(8,6),(8,4),(4,4),(4,6),(0,6))
        r=construct(*model(neck));witness(self,r)
        self.assertEqual([(e.components_before,e.components_after) for e in r.events],[(1,2),(2,0)])

    def test_close_event_times_are_not_merged_by_float_equality(self):
        r=construct(*model(((0,0),(8,Q(1,10**20)),(8,4),(0,4))))
        self.assertEqual(len(r.events),2)
        self.assertLess(r.precision.compare(r.events[0].time,r.events[1].time),0)
        self.assertEqual(r.precision.approximate(r.events[0].time),r.precision.approximate(r.events[1].time))
        witness(self,r)

    def test_certified_seam_compaction_preserves_real_events_and_float_mesh(self):
        from python.audit_line_kernel import record_model,oracle
        r=construct(*record_model(json.loads((ROOT/'python/tests/fixtures/kernel_float_sections.json').read_text())))
        oracle(r);mesh=view(r)
        self.assertLess(len(mesh.vertices),len(r.vertices))
        self.assertTrue(all(v in mesh.source_vertices for e in r.events for v in e.contacts))
        self.assertEqual(mesh.faces,tuple(tuple(mesh.source_vertices.index(v) for v in p.loop) for p in r.patches))

    def test_projected_step_contacts_have_an_independent_area_coverage_proof(self):
        from python.audit_line_kernel import record_model,oracle
        record=json.loads((ROOT/'python/tests/fixtures/kernel_projected_walls.json').read_text())
        r=construct(*record_model(record));proof=oracle(r)
        self.assertLess(proof['coverage_error'],1e-8)
        self.assertLess(proof['outside_error'],1e-8);self.assertLess(proof['overlap_error'],1e-8)
        self.assertEqual(len(view(r,include_walls=True).faces),len(r.patches)+len(r.walls))

    def test_internal_stationary_step_is_not_silently_omitted(self):
        r=construct(*model(((0,0),(8,0),(8,3),(3,3),(3,8),(0,8)),(0,1,3,4)))
        witness(self,r)
        with self.assertRaises(WallRequired):view(r)
        shell=view(r,include_walls=True)
        self.assertEqual(len(shell.faces),len(r.patches)+len(r.walls))
        normal=construct(*model(((0,0),(10,0),(10,3),(3,3),(3,9),(0,9)),(1,4)))
        self.assertEqual(len(view(normal).faces),len(normal.patches))

    def test_exact_kernel_does_not_guarantee_float_mesh_resolution(self):
        r=construct(*model(((0,0),(1,0),(1,Q(1,10**400)),(0,Q(1,10**400))), (1,3)))
        with self.assertRaises(MeshResolutionError):view(r)
        huge=10**400
        translated=construct(*model(((huge,0),(huge+8,0),(huge+8,4),(huge,4)),(1,3)))
        with self.assertRaises(MeshResolutionError):view(translated)


if __name__=='__main__':unittest.main()
