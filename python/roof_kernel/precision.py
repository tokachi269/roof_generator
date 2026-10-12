# SPDX-License-Identifier: GPL-3.0-or-later
"""Filtered signs of rational sums of square roots; no epsilon decisions.

Source line coefficients are rational. Euclidean offset velocities introduce
sqrt(q), q rational and positive. Event coordinates/times are quotients of sums
of such radicals. Distinct rational square classes are linearly independent,
so exact cancellation can be recognized without factoring their numerators.
Nonzero signs are isolated by enclosing intervals with increasing binary bits.
"""
from dataclasses import dataclass,field
from fractions import Fraction as Q
import math

ZERO_Q=Q(0)
ONE_Q=Q(1)


class PrecisionLimit(RuntimeError):
    """Execution incomplete; never an invalid footprint/intent diagnosis."""


def square_root(q):
    n,d=math.isqrt(q.numerator),math.isqrt(q.denominator)
    return Q(n,d) if n*n==q.numerator and d*d==q.denominator else None


@dataclass(frozen=True,eq=False)
class Surd:
    terms: tuple[tuple[Q,Q], ...] = ()

    @classmethod
    def make(cls,terms):
        result=[]
        for q,c in terms:
            q=q if isinstance(q,Q) else Q(q)
            c=c if isinstance(c,Q) else Q(c)
            if not c or not q:continue
            if q<0:raise ValueError('real positive radicals required')
            root=ONE_Q if q==1 else square_root(q)
            if root is not None:q,c=ONE_Q,c*root
            for i,(r,a) in enumerate(result):
                ratio=square_root(q/r)
                if ratio is not None:
                    result[i]=(r,a+c*ratio)
                    break
            else:result.append((q,c))
        return cls(tuple(sorted((q,c) for q,c in result if c)))

    @classmethod
    def number(cls,value):
        if not isinstance(value,Q):value=Q(value)
        return cls(((ONE_Q,value),)) if value else cls()

    @classmethod
    def root(cls,value):return cls.make(((Q(value),Q(1)),))

    def __add__(self,other):
        other=other if isinstance(other,Surd) else Surd.number(other)
        if not self.terms:return other
        if not other.terms:return self
        if len(self.terms)==len(other.terms)==1 and self.terms[0][0]==other.terms[0][0]==1:
            return Surd.number(self.terms[0][1]+other.terms[0][1])
        return Surd.make(self.terms+other.terms)

    __radd__=__add__
    def __neg__(self):return Surd(tuple((q,-c) for q,c in self.terms))
    def __sub__(self,other):return self+-coerce(other)
    def __rsub__(self,other):return coerce(other)+-self
    def __mul__(self,other):
        other=coerce(other)
        if not self.terms or not other.terms:return Surd()
        if len(other.terms)==1 and other.terms[0][0]==1:
            coefficient=other.terms[0][1]
            return Surd(tuple((q,c*coefficient) for q,c in self.terms))
        if len(self.terms)==1 and self.terms[0][0]==1:return other*self
        return Surd.make((q*r,a*b) for q,a in self.terms for r,b in other.terms)

    __rmul__=__mul__
    def __eq__(self,other):return not (self-coerce(other)).terms
    __hash__=None


def coerce(value):return value if isinstance(value,Surd) else Surd.number(value)


ONE=Surd.number(1)  # Immutable arithmetic identity, not mutable cached state.


@dataclass(frozen=True,eq=False)
class Scalar:
    numerator: Surd
    denominator: Surd = field(default_factory=lambda:ONE)

    def __post_init__(self):
        if not self.denominator.terms:raise ZeroDivisionError('zero radical denominator')
        if not self.numerator.terms:
            object.__setattr__(self,'denominator',ONE)
        elif len(self.denominator.terms)==1 and self.denominator.terms[0][0]==1:
            d=self.denominator.terms[0][1]
            if d!=1:object.__setattr__(self,'numerator',Surd(tuple((q,c/d) for q,c in self.numerator.terms)))
            object.__setattr__(self,'denominator',ONE)

    @classmethod
    def number(cls,value):return cls(coerce(value))
    def rational(self):
        if not self.numerator.terms:return ZERO_Q
        if len(self.numerator.terms)==1 and self.numerator.terms[0][0]==1 and \
           self.denominator.terms==ONE.terms:return self.numerator.terms[0][1]
        return None
    def __neg__(self):return Scalar(-self.numerator,self.denominator)
    def __add__(self,other):
        other=scalar(other)
        a,b=self.rational(),other.rational()
        if a is not None and b is not None:return Scalar.number(a+b)
        if self.denominator.terms==other.denominator.terms or self.denominator==other.denominator:
            return Scalar(self.numerator+other.numerator,self.denominator)
        return Scalar(self.numerator*other.denominator+other.numerator*self.denominator,
                      self.denominator*other.denominator)
    __radd__=__add__
    def __sub__(self,other):return self+-scalar(other)
    def __rsub__(self,other):return scalar(other)+-self
    def __mul__(self,other):
        other=scalar(other)
        a,b=self.rational(),other.rational()
        if a is not None and b is not None:return Scalar.number(a*b)
        if not self.numerator.terms or not other.numerator.terms:return Scalar.number(0)
        return Scalar(self.numerator*other.numerator,self.denominator*other.denominator)
    __rmul__=__mul__
    def __truediv__(self,other):
        other=scalar(other)
        if not other.numerator.terms:raise ZeroDivisionError('exact zero scalar')
        a,b=self.rational(),other.rational()
        if a is not None and b is not None:return Scalar.number(a/b)
        return Scalar(self.numerator*other.denominator,self.denominator*other.numerator)
    def __eq__(self,other):return not (self-scalar(other)).numerator.terms
    __hash__=None


def scalar(value):return value if isinstance(value,Scalar) else Scalar.number(value)


def _float_bounds(q):
    f=float(q)
    if not math.isfinite(f):raise OverflowError
    exact=Q(f)
    return (f if exact<=q else math.nextafter(f,-math.inf),
            f if exact>=q else math.nextafter(f,math.inf))


class Precision:
    def __init__(self,*,max_bits=4096):
        if max_bits<64:raise ValueError('precision budget must be at least 64 bits')
        self.max_bits=max_bits
        self.double_signs=self.rational_signs=self.refinements=self.exact_zeros=0
        self.bits_used=0
        self.roots={}

    def _double_root(self,q):
        key=(q,0)
        if key in self.roots:return self.roots[key]
        raw=float(q)
        if raw<=0 or not math.isfinite(raw):raise OverflowError
        f=math.sqrt(raw)
        if not math.isfinite(f):raise OverflowError
        lo,hi=f,f
        # Certify both square-root bounds with rational arithmetic. Do not
        # assume sqrt or conversion had a particular rounding error.
        for _ in range(4):
            if Q(lo)*Q(lo)<=q:break
            lo=math.nextafter(lo,-math.inf)
        else:raise OverflowError
        for _ in range(4):
            if Q(hi)*Q(hi)>=q:break
            hi=math.nextafter(hi,math.inf)
        else:raise OverflowError
        self.roots[key]=(lo,hi)
        return lo,hi

    def _double_interval(self,value):
        lo=hi=0.
        for q,c in value.terms:
            a,b=self._double_root(q);u,v=_float_bounds(c)
            products=(a*u,a*v,b*u,b*v)
            product_lo=math.nextafter(min(products),-math.inf)
            product_hi=math.nextafter(max(products),math.inf)
            lo=math.nextafter(lo+product_lo,-math.inf)
            hi=math.nextafter(hi+product_hi,math.inf)
            if not math.isfinite(lo) or not math.isfinite(hi):raise OverflowError
        return lo,hi

    def interval(self,value,bits):
        lo=hi=Q(0)
        for q,c in value.terms:
            key=(q,bits)
            if key not in self.roots:
                k=math.isqrt((q.numerator<<(2*bits))//q.denominator)
                a=Q(k,1<<bits)
                b=a if a*a==q else Q(k+1,1<<bits)
                self.roots[key]=(a,b)
            a,b=self.roots[key]
            if c<0:a,b=b,a
            lo+=c*a;hi+=c*b
        return lo,hi

    def sign(self,value):
        if isinstance(value,Scalar):
            rational=value.rational()
            if rational is not None:
                if not rational:self.exact_zeros+=1;return 0
                self.rational_signs+=1;return 1 if rational>0 else -1
            if not value.numerator.terms:
                self.exact_zeros+=1;return 0
            return self.sign(value.numerator)*self.sign(value.denominator)
        value=coerce(value)
        if not value.terms:
            self.exact_zeros+=1;return 0
        if len(value.terms)==1 and value.terms[0][0]==1:
            self.rational_signs+=1;return 1 if value.terms[0][1]>0 else -1
        try:
            lo,hi=self._double_interval(value)
            if lo>0:self.double_signs+=1;return 1
            if hi<0:self.double_signs+=1;return -1
        except (OverflowError,ValueError):pass
        self.refinements+=1
        bits=64
        while bits<=self.max_bits:
            self.bits_used=max(self.bits_used,bits)
            lo,hi=self.interval(value,bits)
            if lo>0:return 1
            if hi<0:return -1
            bits*=2
        raise PrecisionLimit('nonzero radical sign exceeded the precision budget')

    def compare(self,a,b):
        a,b=scalar(a),scalar(b)
        x,y=a.rational(),b.rational()
        if x is not None and y is not None:
            if x==y:self.exact_zeros+=1;return 0
            self.rational_signs+=1;return 1 if x>y else -1
        return self.sign(a-b)

    def rational_interval(self,value,bits=128):
        value=scalar(value)
        a,b=self.interval(value.numerator,bits)
        c,d=self.interval(value.denominator,bits)
        if c<=0<=d:
            if bits*2>self.max_bits:raise PrecisionLimit('denominator isolation incomplete')
            return self.rational_interval(value,bits*2)
        products=(a/c,a/d,b/c,b/d)
        return min(products),max(products)

    def approximate(self,value):
        value=scalar(value)
        rational=value.rational()
        if rational is not None:return float(rational)
        bits=min(128,self.max_bits)
        while bits<=self.max_bits:
            a,b=self.rational_interval(value,bits)
            left,right=float(a),float(b)
            if left==right:return left
            if math.nextafter(left,math.inf)==right:
                midpoint=(Q(left)+Q(right))/2
                comparison=self.compare(value,midpoint)
                if comparison<0:return left
                if comparison>0:return right
                return float(midpoint)  # Python's correctly rounded ties-to-even.
            bits*=2
        raise PrecisionLimit('floating-point rounding is not certified within the precision budget')

    def inspect(self):
        return {k:getattr(self,k) for k in ('double_signs','rational_signs','refinements','exact_zeros','bits_used')}
