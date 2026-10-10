# SPDX-License-Identifier: GPL-3.0-or-later
"""Exterior intent from declared region axes, independent of skeleton events.

This contract projects rectangular roof interpretations onto the actual
footprint boundary. It creates no internal junctions or roof primitives. A
cap-only backend must report mixed intervals and unavailable gable ends; it
cannot replace them by whichever ends its implementation happens to support.
"""
from dataclasses import asdict, dataclass
from itertools import combinations
import math


class IntentError(ValueError):
    pass


@dataclass(frozen=True)
class IntervalIntent:
    edge: int
    interval: tuple[float, float]
    kind: str
    member: int
    side: int


@dataclass(frozen=True)
class CapIntent:
    selected: tuple[int, ...]
    gaps: tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class CapConfiguration:
    selected: tuple[int, ...]
    axis_domains: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class CapPool:
    configurations: tuple[CapConfiguration, ...]
    complete: bool
    work: int
    reason: str | None = None


@dataclass(frozen=True)
class TerminalDomain:
    opposed_edges: tuple[int, ...]
    triangular_caps: tuple[int, ...]
    conflicts: tuple[tuple[int, int], ...]
    blocked_caps: tuple[int, ...]


def opposed_supports(fp, edge):
    """Actual neighboring inward normals; numerical allowance, no rectification."""
    from .footprint import EPS
    normals=[];lengths=[]
    for support in ((edge-1)%len(fp.vertices),(edge+1)%len(fp.vertices)):
        a,b=fp.vertices[support],fp.vertices[(support+1)%len(fp.vertices)]
        size=math.dist(a,b)
        lengths.append(size)
        normals.append((-(b[1]-a[1])/size,(b[0]-a[0])/size))
    # Coordinate noise induces an angle error inversely proportional to edge
    # length. Bound it by the existing positional allowance and a float32-scale
    # ceiling; this never rotates a support line or rectifies an input corner.
    tolerance=min(1e-6,max(1e-8,8*EPS*sum(1/size for size in lengths)))
    return math.dist(normals[0],tuple(-x for x in normals[1]))<=tolerance


def cap_parameter(fp, edge):
    """Equal-distance locus on the actual cap, including bounded input rounding."""
    from .footprint import sub, cross
    from .errors import UnsupportedRoofError
    n=len(fp.vertices);a,b=fp.vertices[edge],fp.vertices[(edge+1)%n]
    left=sub(a,fp.vertices[(edge-1)%n]);right=sub(fp.vertices[(edge+2)%n],b)
    dl=cross(left,sub(b,a))/math.hypot(*left)
    dr=cross(right,sub(a,b))/math.hypot(*right)
    if dl<=0 or dr<=0:
        raise UnsupportedRoofError('terminal cap lacks positive interior support distances')
    if abs(dl-dr)<=1e-12*max(dl,dr):return .5
    return dr/(dl+dr)


@dataclass(frozen=True)
class RoofIntent:
    region_id: str
    source: str
    axes: tuple[int, ...]
    intervals: tuple[IntervalIntent, ...]
    outline: tuple[tuple[float, float], ...]

    @property
    def edge_count(self):
        return len(self.outline)

    @classmethod
    def declare(cls, layout, axes, ends=None):
        from .footprint import EPS
        from .roof_ends import End, EndShape
        axes = tuple(axes)
        if len(axes) != len(layout.supports) or any(a not in (0, 1) for a in axes):
            raise IntentError('one explicit ridge axis required per region')
        intervals = []
        used_ends = set()
        for member, axis in zip(layout.supports, axes):
            for side_index, side in enumerate(member.sides):
                a, b = (layout.vertices[i] for i in side.vertices)
                if min(abs(a[0]-b[0]), abs(a[1]-b[1])) > 4*EPS:
                    raise IntentError('intent requires axis-aligned rectangular model sides')
                direction = 0 if abs(a[0]-b[0]) > abs(a[1]-b[1]) else 1
                kind = 'eave'
                if direction != axis and side.exterior:
                    end = End(member.id, side_index); used_ends.add(end)
                    shape = EndShape.GABLE if ends is None else ends.get(end)
                    if shape not in (EndShape.GABLE, EndShape.HIP):
                        raise IntentError('each exterior short end needs an explicit gable or hip state')
                    kind = 'gable_end' if shape == EndShape.GABLE else 'eave'
                intervals.extend(IntervalIntent(span.edge, span.interval, kind, member.id, side_index)
                                 for span in side.exterior)
        if ends is not None and set(ends) != used_ends:
            raise IntentError('end states refer to a different set of exterior short ends')
        intervals.sort(key=lambda i: (i.edge, i.interval))
        for edge in range(len(layout.footprint.vertices)):
            cursor = 0.
            for item in (i for i in intervals if i.edge == edge):
                lo, hi = item.interval
                if abs(lo-cursor) > 4*EPS or hi <= lo:
                    raise IntentError('exterior intent has a gap or overlapping ownership')
                cursor = hi
            if abs(cursor-1.) > 4*EPS:
                raise IntentError('exterior intent does not cover the footprint')
        return cls(layout.candidate.id, layout.candidate.source, axes,
                   tuple(intervals), layout.footprint.vertices)

    @classmethod
    def from_caps(cls, layout, axes, selected):
        """Resolve a proposed global end set against region model directions.

        The caller proposes end choices. No long side may become a gable, and
        separate exposed pieces of one physical short end must share a state.
        Unselected short ends are explicitly HIP, not silently discarded
        gable requests. This is a mixed hip/gable model domain, not pure gable.
        """
        from .roof_ends import End, EndShape
        axes = tuple(axes); selected = frozenset(selected)
        if len(axes) != len(layout.supports) or any(a not in (0,1) for a in axes):
            raise IntentError('one explicit ridge axis required per region')
        if not selected or not selected <= set(range(len(layout.footprint.vertices))):
            raise IntentError('nonempty exterior cap selection required')
        ends = {}
        for member, axis in zip(layout.supports,axes):
            for index, side in enumerate(member.sides):
                if not side.exterior: continue
                a,b = (layout.vertices[i] for i in side.vertices)
                direction = 0 if abs(a[0]-b[0])>abs(a[1]-b[1]) else 1
                shapes = {EndShape.GABLE if span.edge in selected else EndShape.HIP
                          for span in side.exterior}
                if direction == axis:
                    if EndShape.GABLE in shapes:
                        raise IntentError('gable selection contradicts a declared region eave side')
                else:
                    if len(shapes) != 1:
                        raise IntentError('one physical short end has inconsistent exposed states')
                    ends[End(member.id,index)] = next(iter(shapes))
        return cls.declare(layout,axes,ends)

    @staticmethod
    def axis_domains(layout, selected, model='mixed'):
        """Factor the exact exterior constraints without enumerating free axes.

        For mixed models an unselected short end is HIP. For pure gable models
        an unselected exterior interval must be a long eave side. Each member
        is independent at this exterior-only boundary; internal junction rules
        are deliberately absent. Empty domains reject, never repair the intent.
        """
        from .footprint import EPS
        if model not in ('mixed','gable'):
            raise IntentError('explicit mixed or gable model required')
        selected = frozenset(selected)
        if not selected or not selected <= set(range(len(layout.footprint.vertices))):
            raise IntentError('nonempty exterior cap selection required')
        domains = []
        for member in layout.supports:
            domain = {0,1}
            for side in member.sides:
                if not side.exterior: continue
                a,b = (layout.vertices[i] for i in side.vertices)
                if min(abs(a[0]-b[0]),abs(a[1]-b[1]))>4*EPS:
                    raise IntentError('intent requires axis-aligned rectangular model sides')
                direction = 0 if abs(a[0]-b[0])>abs(a[1]-b[1]) else 1
                states = {span.edge in selected for span in side.exterior}
                if len(states)!=1:
                    domain.clear()
                elif states == {True}:
                    domain.intersection_update((1-direction,))
                elif model == 'gable':
                    domain.intersection_update((direction,))
            domains.append(tuple(sorted(domain)))
        return tuple(domains)

    def inspect(self):
        return asdict(self)

    def caps(self, available):
        """Translate whole-edge intent; preserve every unrepresentable request."""
        available = frozenset(available)
        selected, gaps = [], []
        for edge in range(self.edge_count):
            kinds = {i.kind for i in self.intervals if i.edge == edge}
            if len(kinds) != 1:
                gaps.append((edge, 'mixed eave/gable intervals'))
            elif kinds == {'gable_end'}:
                if edge in available:
                    selected.append(edge)
                else:
                    gaps.append((edge, 'gable end is not an ordinary terminal cap'))
        if not selected:
            gaps.append((-1, 'no representable gable end'))
        return CapIntent(tuple(selected), tuple(gaps))

    def verify(self, graph):
        """Observe graph boundary incidence, never change it to fit the guide."""
        from .footprint import EPS
        if graph.outline != self.outline:
            raise IntentError('graph belongs to a different exterior boundary')
        for expected in self.intervals:
            lo, hi = expected.interval
            for edge in graph.edges:
                span = edge.boundary
                if span is None or span.edge != expected.edge:
                    continue
                if min(hi, span.interval[1])-max(lo, span.interval[0]) > 4*EPS:
                    if edge.kind != expected.kind:
                        raise IntentError('constructed boundary contradicts declared intent')


def cap_domain(fp, skeleton):
    """Expose the existing disk rewrite's support conditions before selection.

    Shared node identity alone is not a conflict: opposite square caps can
    coexist. A conflict exists when selecting one disk would consume a slope
    sector needed by another. These are construction constraints, not new
    architectural relation names or a priority between ends.
    """
    loops = list(skeleton.faces)
    n = len(fp.vertices)
    if any(f[0]>=n or f[1]!=(f[0]+1)%n for f in loops):
        raise IntentError('skeleton original-edge identity changed')
    caps = {f[0]:f[2] for f in loops if len(f)==3 and f[2]>=n}
    conflicts = set(); blocked = set()
    for edge,node in caps.items():
        if not opposed_supports(fp,edge):
            blocked.add(edge)
        for pair in ((node,(edge+1)%n),(edge,node)):
            owners=[f[0] for f in loops if f[0]!=edge and pair in tuple(zip(f,f[1:]+f[:1]))]
            if len(owners)!=1:
                blocked.add(edge)
            elif owners[0] in caps:
                conflicts.add(tuple(sorted((edge,owners[0]))))
    return tuple(sorted(caps)),tuple(sorted(conflicts)),tuple(sorted(blocked))


def terminal_configurations(available, conflicts=(), blocked=(), *, max_work=65536, max_candidates=4096):
    """All maximal compatible terminal ends, without rectangular axis guesses.

    Bron–Kerbosch enumerates maximal cliques in the compatibility graph, hence
    maximal independent sets in the disk conflict graph. Maximality is the same
    componentwise gable-over-hip order as the rectangular intent producer.
    Budgets invalidate the entire family, never expose a selectable prefix.
    """
    if max_work<1 or max_candidates<1:
        raise ValueError('positive terminal model budgets required')
    vertices=set(available)-set(blocked)
    neighbors={v:vertices-{v} for v in vertices}
    for a,b in conflicts:
        if a in vertices and b in vertices:
            neighbors[a].discard(b);neighbors[b].discard(a)
    result=[];work=0;reason=None

    def visit(selected, pending, excluded):
        nonlocal work, reason
        work+=1
        if work>max_work:
            reason='terminal model work budget exhausted';return
        if not pending and not excluded:
            if selected:
                result.append(CapConfiguration(tuple(sorted(selected)),()))
                if len(result)>max_candidates:reason='terminal roof candidate budget exhausted'
            return
        pivot=min(pending|excluded,key=lambda v:(-len(pending&neighbors[v]),v))
        for vertex in sorted(pending-neighbors[pivot]):
            visit(selected|{vertex},pending&neighbors[vertex],excluded&neighbors[vertex])
            if reason:return
            pending.remove(vertex);excluded.add(vertex)

    visit(set(),set(vertices),set())
    return CapPool(() if reason else tuple(sorted(result,key=lambda c:c.selected)),not bool(reason),work,reason)


def subtract_domain(domain, removed):
    """Exact disjoint cube difference for finite per-member axis domains."""
    overlap=tuple(tuple(v for v in a if v in b) for a,b in zip(domain,removed))
    if not all(overlap): return (domain,)
    pieces=[]
    for index,(a,b) in enumerate(zip(domain,overlap)):
        rest=tuple(v for v in a if v not in b)
        if rest:
            pieces.append(overlap[:index]+(rest,)+domain[index+1:])
    return tuple(pieces)


def gable_configurations(layout, available, conflicts=(), blocked=(), *, axes=None, max_work=65536):
    """All maximal compatible gable choices, separately for every axis model.

    GABLE is preferred to HIP at each exterior end for a gable request. This
    componentwise order adds no metric/appearance score. A smaller end set is
    removed only for those axis assignments where a strict superset satisfies
    the same region model and disk support constraints. Ambiguous maximal
    choices all survive; no first choice or largest-cardinality selection.

    The finite cap backend still cannot fulfill nonterminal/partial gables.
    This is an explicit mixed model comparison, not a pure-gable completion.
    """
    if max_work<1:raise ValueError('positive cap-domain work budget required')
    axes=tuple(axes) if axes is not None else ((0,1),)*len(layout.supports)
    if len(axes)!=len(layout.supports) or any(not a or not set(a)<={0,1} for a in axes):
        raise IntentError('one nonempty explicit axis domain required per region')
    available=tuple(sorted(set(available)-set(blocked)))
    work=0;feasible=[];result=[]
    for count in range(1,len(available)+1):
        for selected in combinations(available,count):
            work+=1
            if work>max_work:return CapPool((),False,work,'cap-domain work budget exhausted')
            if any(a in selected and b in selected for a,b in conflicts):continue
            domains=tuple(tuple(v for v in a if v in b) for a,b in zip(
                RoofIntent.axis_domains(layout,selected),axes))
            if all(domains):feasible.append((selected,domains))
    for selected,domains in feasible:
        remainder=(domains,)
        for larger,other in feasible:
            work+=1
            if work>max_work:return CapPool((),False,work,'cap dominance work budget exhausted')
            if len(larger)<=len(selected) or not set(selected)<set(larger):continue
            remainder=tuple(part for cube in remainder for part in subtract_domain(cube,other))
            if not remainder:break
        result.extend(CapConfiguration(selected,cube) for cube in remainder)
    return CapPool(tuple(result),True,work)
