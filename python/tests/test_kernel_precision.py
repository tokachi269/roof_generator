# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact-zero and certified nonzero decisions, independent rational witnesses."""
from fractions import Fraction as Q
from decimal import Decimal,localcontext
import random
import unittest
from python.roof_kernel.precision import Precision,PrecisionLimit,Surd,Scalar
from python.roof_kernel.boundary import BoundaryPath,Line,RoofIntent,InvalidBoundary,InvalidIntent,UnspecifiedModel
from python.roof_kernel.sources import prepare,trajectory
from python.roof_kernel.admissibility import necessary_coverage,InconsistentIntent


def path(points):
    points=tuple(points)
    return BoundaryPath(tuple(Line(str(i),a,b) for i,(a,b) in enumerate(zip(points,points[1:]+points[:1]))))


class KernelPrecision(unittest.TestCase):
    def test_exact_radical_identities_and_quotients(self):
        p=Precision()
        self.assertEqual(p.sign(Surd.root(8)-2*Surd.root(2)),0)
        self.assertEqual(p.sign(Surd.root(Q(18,25))-Q(3,5)*Surd.root(2)),0)
        left=Scalar(Surd.number(1),Surd.root(2)+Surd.root(3))
        right=Scalar.number(Surd.root(3)-Surd.root(2))
        self.assertEqual(p.compare(left,right),0)
        self.assertEqual(p.sign((Surd.root(2)+Surd.root(3))*(Surd.root(2)-Surd.root(3))+1),0)

    def test_uncertain_double_sign_refines_without_a_tolerance(self):
        p=Precision()
        tiny=Surd.root(1+Q(1,1<<300))-1
        self.assertEqual(p.sign(tiny),1)
        self.assertEqual(p.sign(-tiny),-1)
        self.assertGreater(p.refinements,0);self.assertGreaterEqual(p.bits_used,512)
        with self.assertRaises(PrecisionLimit):Precision(max_bits=128).sign(tiny)
        self.assertEqual(p.sign(Surd.root(Q(1,10**900))),1)

    def test_export_rounding_is_certified_including_halfway_values(self):
        midpoint=Q(1)+Q(1,1<<53)
        hidden=Scalar(Surd.root(2)*midpoint,Surd.root(2))
        tiny=Scalar.number(Surd.root(1+Q(1,1<<300))-1)
        p=Precision()
        self.assertEqual(p.approximate(hidden),1.)
        self.assertEqual(p.approximate(hidden+tiny),1.+2.**-52)
        self.assertEqual(p.approximate(hidden-tiny),1.)
        with self.assertRaises(PrecisionLimit):Precision(max_bits=128).approximate(hidden+tiny)
        self.assertEqual(Precision(max_bits=64).approximate(Surd.root(2)),float(Decimal(2).sqrt()))

    def test_random_enclosures_against_decimal_and_rational_square_bounds(self):
        rng=random.Random(721)
        p=Precision()
        with localcontext() as ctx:
            ctx.prec=120
            for _ in range(100):
                terms=[(Q(rng.randint(1,100),rng.randint(1,100)),Q(rng.randint(-40,40),rng.randint(1,12))) for _ in range(5)]
                value=Surd.make(terms)
                expected=sum(Decimal(c.numerator)/Decimal(c.denominator)*(Decimal(q.numerator)/Decimal(q.denominator)).sqrt()
                             for q,c in terms)
                sign=1 if expected>0 else -1 if expected<0 else 0
                self.assertEqual(p.sign(value),sign)
                lo,hi=p.interval(value,128)
                self.assertLessEqual(Decimal(lo.numerator)/Decimal(lo.denominator),expected)
                self.assertGreaterEqual(Decimal(hi.numerator)/Decimal(hi.denominator),expected)

    def test_exact_boundary_preserves_collinear_source_identity(self):
        p=path(((0,0),(3,0),(8,0),(8,5),(0,5)))
        intent=RoofIntent(tuple((s.id,'EAVE') for s in p.sources))
        frame,planes,cycles,ring=prepare(p,intent)
        self.assertEqual(len(p.sources),5);self.assertEqual(len(cycles[0]),4)
        self.assertIn(('0','1'),[plane.sources for plane in planes])
        mixed=RoofIntent((('0','EAVE'),('1','GABLE'),('2','EAVE'),('3','EAVE'),('4','EAVE')))
        with self.assertRaises(UnspecifiedModel):prepare(p,mixed)
        with self.assertRaises(InvalidBoundary):path(((0,0),(4,4),(0,4),(4,0)))
        with self.assertRaises(InvalidIntent):prepare(p,RoofIntent((('0','EAVE'),)))

    def test_nonexistence_is_a_rational_point_certificate_not_kernel_failure(self):
        p=path(((0,0),(8,0),(8,3),(3,3),(3,8),(0,8)))
        intent=RoofIntent(tuple((s.id,'EAVE' if s.id=='3' else 'GABLE') for s in p.sources))
        frame,planes,cycles,ring=prepare(p,intent)
        with self.assertRaises(InconsistentIntent) as error:necessary_coverage(ring,planes,frame)
        certificate=error.exception.certificate
        x,y=map(Q,certificate['point'])
        self.assertGreater(x,3);self.assertLess(x,8);self.assertGreater(y,0);self.assertLess(y,3)
        self.assertEqual(certificate['kind'],'no_nonnegative_source_plane')


if __name__=='__main__':unittest.main()
