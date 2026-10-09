# SPDX-License-Identifier: GPL-3.0-or-later
"""Opposite receiving slopes: analytic incidence witness and domain counterexample."""
from pathlib import Path
import math
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'addon'))
from roof_generator.core.footprint import analyze
from roof_generator.core.roof_regions import propose_regions
from roof_generator.core.region_architecture import interpret_regions
from roof_generator.core.architecture import resolve
from roof_generator.core.roof_ends import roof_configurations
from roof_generator.core.topology import compose
from roof_generator.core.mesh import RoofMesh
from roof_generator.core.junctions import plan
from roof_generator.core.topology import member_templates
from roof_generator.core.errors import UnsupportedRoofError


def arrangement(low=3,high=6,bottom_width=3):
    fp=analyze(((2,0),(8,0),(8,bottom_width),(7,bottom_width),(7,6),(8,6),(8,8),
                (2,8),(2,high),(1,high),(1,low),(2,low)))
    regions=(((1,low),(2,low),(2,high),(1,high)),((2,0),(7,0),(7,8),(2,8)),
             ((7,0),(8,0),(8,bottom_width),(7,bottom_width)),((7,6),(8,6),(8,8),(7,8)))
    architecture=interpret_regions(propose_regions(fp,regions,source='opposite-eaves'))
    horizontal=int(abs(fp.frame.direction[1])>.5)
    central=next(i for i,r in enumerate(architecture.layout.candidate.regions)
                 if len(r.boundary)==4 and abs(r.area-40/fp.frame.scale**2)<1e-9)
    axes=tuple(1-horizontal if i==central else horizontal for i in range(4))
    authority=resolve(architecture,axes)
    ends=next(e for e in roof_configurations(authority)
              if sorted(j.kind for j in e.joints)==['extension','shared','shared'])
    return authority.with_ends(ends)


class OppositeSlopeProof(unittest.TestCase):
    def test_literal_embedding_does_not_use_solver_to_choose_incidence(self):
        authority=arrangement()
        composition=compose(authority)
        fp=authority.layout.footprint
        # The five free interior nodes follow equal pitch: the main half-width
        # is 2.5, branch half-widths are 1.5, 1.5 and 1. No nonlinear oracle.
        expected=((*((x,y,0) for x,y in ((7,6),(8,6),(8,8),(2,8),(2,6),(1,6),
                                       (1,3),(2,3),(2,0),(8,0),(8,3),(7,3))),
                  (1,4.5,.75),(8,1.5,.75),(8,7,.5),(3.5,4.5,.75),
                  (4.5,2.5,1.25),(5.5,1.5,.75),(4.5,5.5,1.25),(6,7,.5)))
        self.assertEqual(len(composition.graph.vertices),len(expected))
        seeds=tuple(fp.frame.world_xy(v.seed) for v in composition.graph.vertices)
        # Initial free-node positions are unrelated to the analytic witness;
        # the incidence's fixed nodes alone determine this literal mapping.
        for i,v in enumerate(composition.graph.vertices):
            if v.boundary is not None:self.assertLess(math.dist(seeds[i],expected[i][:2]),1e-8)
        def intrinsic(p):
            delta=tuple(p[k]-fp.frame.origin[k] for k in (0,1))
            ux,uy=fp.frame.direction
            return (*(sum(delta[k]*axis[k] for k in (0,1))/fp.frame.scale
                       for axis in ((ux,uy),(-uy,ux))),p[2]/fp.frame.scale)
        intrinsic=tuple(intrinsic(p) for p in expected)
        mesh=RoofMesh(composition.graph,intrinsic)
        self.assertEqual(len(mesh.faces),8)
        self.assertEqual({c.kind for c in composition.connections},{'terminal','middle'})
        for edge in mesh.graph.edges:
            if edge.kind=='valley':
                self.assertGreater(max(mesh.vertices[v][2] for v in edge.vertices),0)
        for face in mesh.faces:
            a,b,c=(mesh.vertices[i] for i in face[:3])
            u=tuple(b[k]-a[k] for k in range(3));v=tuple(c[k]-a[k] for k in range(3))
            normal=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
            if abs(normal[2])>1e-10:
                self.assertAlmostEqual(math.hypot(*normal[:2])/abs(normal[2]),.5)

    def test_equal_width_terminal_is_outside_strictly_lower_proof(self):
        authority=arrangement(bottom_width=5)
        with self.assertRaisesRegex(UnsupportedRoofError,'mixed junction neighborhoods interact'):
            plan(authority,member_templates(authority))


if __name__=='__main__':unittest.main()
