# SPDX-License-Identifier: GPL-3.0-or-later
"""The runtime publisher consumes explicit whole-polygon models upstream."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'addon'))
from roof_generator.core.footprint import analyze
from roof_generator.core.polygon_roof import PolygonRoof,topology
from roof_generator.core.wavefront import wavefront,WavefrontBudget
from roof_generator.core.solve import problem,solve
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.vendor.straight_skeleton import algorithm,compute_skeleton
from roof_generator.core import graph as graph_api
from roof_generator.core.provenance import BoundaryPoint
from python.whole_polygon_roofs import topology as reference_topology
from types import SimpleNamespace
from roof_generator.vendor.straight_skeleton.skeleton import Skeleton
from roof_generator.vendor.straight_skeleton.vector_math import Vector2


class PolygonRuntime(unittest.TestCase):
    def test_invalid_foreign_face_cycle_is_bounded_without_geometry_repair(self):
        points=((0,0),(1,0),(1,1),(2,1),(1.5,2))
        nodes=[SimpleNamespace(_skn_id=i,position=Vector2(*p),time=0 if i<2 else 1)
               for i,p in enumerate(points)]
        foreign=SimpleNamespace(_faces=None,_sk_nodes_all=nodes,_sk_original_edges=[(0,1)],
                                _arcs_by_node={1:[2],2:[3],3:[4],4:[2]})
        with self.assertRaisesRegex(RuntimeError,'repeats an arc'):
            Skeleton._compute_faces_if_needed(foreign)
        self.assertIsNone(foreign._faces)

    def test_explicit_polygon_model_keeps_graph_fixed_through_pitch_and_height(self):
        fp=analyze([(0,0),(12,0),(12,6),(0,6)])
        data=wavefront(fp)
        caps=tuple(sorted(f[0] for f in data.faces if len(f)==3))
        model=PolygonRoof(fp,caps)
        graph,_=topology(model,data)
        with self.assertRaises(TypeError):topology(fp,data)
        for pitch in (.2,.5,.8):
            mesh=solve(graph,problem(graph,pitch,2/fp.frame.scale))
            self.assertIs(mesh.graph,graph)
            self.assertEqual(mesh.faces,tuple(f.loop for f in graph.faces))
            self.assertEqual(sum(e.kind=='valley' for e in graph.edges),0)
        self.assertEqual(len(graph.faces),2)
        self.assertEqual(model.inspect()['regions'],[fp.vertices])
        self.assertEqual({v.cells for v in graph.vertices},{(0,)})

    def test_shared_event_requires_explicit_compatible_ends_without_automatic_hip_repair(self):
        fp=analyze([(0,0),(10,0),(10,10),(0,10)]);data=wavefront(fp)
        for ends in ((0,2),(1,3)):
            graph,_=topology(PolygonRoof(fp,ends),data)
            self.assertEqual(sum(e.kind=='ridge' for e in graph.edges),1)
            self.assertEqual(sum(e.kind=='hip' for e in graph.edges),0)
            self.assertIs(solve(graph,problem(graph)).graph,graph)
        with self.assertRaisesRegex(UnsupportedRoofError,'incident slope sectors'):
            topology(PolygonRoof(fp,(0,1)),data)
        with self.assertRaises(UnsupportedRoofError):PolygonRoof(fp,())

    def test_budget_restores_runtime_state_and_threaded_incidence_is_deterministic(self):
        fp=analyze([(0,0),(12,0),(12,6),(0,6)])
        previous=algorithm.GLOBAL_ALGORITHM_TRACER
        with self.assertRaises(WavefrontBudget):wavefront(fp,max_work=1)
        self.assertIs(algorithm.GLOBAL_ALGORITHM_TRACER,previous)
        with ThreadPoolExecutor(max_workers=4) as executor:
            results=list(executor.map(lambda _:wavefront(fp),range(8)))
        self.assertTrue(all(result==results[0] for result in results))
        self.assertIs(algorithm.GLOBAL_ALGORITHM_TRACER,previous)

    def test_runtime_incidence_matches_the_previously_verified_constructor(self):
        outlines=([(0,0),(12,0),(12,6),(0,6)],
                  [(0,0),(16,0),(16,4),(10,4),(10,10),(6,10),(6,4),(0,4)])
        for outline in outlines:
            fp=analyze(outline);data=wavefront(fp)
            ends=tuple(sorted(f[0] for f in data.faces if len(f)==3))
            graph,_=topology(PolygonRoof(fp,ends),data)
            expected,_=reference_topology(fp,compute_skeleton,graph_api,BoundaryPoint,
                                         UnsupportedRoofError,selected_caps=ends)
            self.assertEqual(graph,expected)


if __name__=='__main__':unittest.main()
