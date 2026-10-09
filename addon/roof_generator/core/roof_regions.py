# SPDX-License-Identifier: GPL-3.0-or-later
"""Polygon support authority for proposals. 2D acceptance is not roof validity.

All sources use propose_regions; no source wins by order or implementation
availability. Coordinates in accepted records use the footprint's intrinsic
frame. Cell intersections are provenance only. No roof graph or seed choice.
"""
from dataclasses import asdict, dataclass
import math

from .errors import UnsupportedRoofError
from .footprint import EPS, Footprint, analyze, area, inside, rectangle
from .seed import derive, point_identity


@dataclass(frozen=True)
class CellOverlap:
    cell: int
    area: float  # intrinsic area, not a membership claim


@dataclass(frozen=True)
class RoofRegion:
    boundary: tuple[tuple[float, float], ...]
    provenance: tuple[CellOverlap, ...] = ()

    @property
    def area(self):
        return abs(area(self.boundary))


@dataclass(frozen=True)
class RoofRegionCandidate:
    footprint: Footprint
    regions: tuple[RoofRegion, ...]
    source: str
    id: str  # geometry identity only; not an eventual roof candidate identity

    def inspect(self):
        return {'id': self.id, 'source': self.source,
                'regions': [asdict(r) for r in self.regions],
                'validation_stage': '2D support only', 'roof_topology': None}


@dataclass(frozen=True)
class RegionRecommendation:
    score: int | None
    parallel_contacts: tuple[tuple[int, int], ...]
    unscored_regions: tuple[int, ...]


def _interior(ring):
    # Exact axis-aligned rectangles have the same open interior as their box.
    # Keep the polygon predicate for rotated/toleranced or compound supports.
    xs={p[0] for p in ring};ys={p[1] for p in ring}
    if len(xs)==len(ys)==2 and rectangle(ring):
        x0,x1=sorted(xs);y0,y1=sorted(ys)
        return lambda p:x0<p[0]<x1 and y0<p[1]<y1
    return lambda p:inside(p,ring)


def parallel_recommendation(candidate, axes):
    """Hu parallel term only, for declared long-axis rectangular roof supports.

    It is neither a general polygon score nor a roof-validity check. Any support
    outside that published domain leaves the whole score unknown, not zero.
    Axes are explicit model directions, never read from Cell provenance.
    """
    if len(axes)!=len(candidate.regions) or any(a not in (0,1) for a in axes):
        raise ValueError('one declared orthogonal model axis is required per region')
    bounds = [tuple(f(r.boundary,key=lambda p:p[k])[k]
                    for f,k in ((min,0),(min,1),(max,0),(max,1)))
              for r in candidate.regions]
    unscored = tuple(i for i,(r,b,a) in enumerate(zip(candidate.regions,bounds,axes))
                     if len(r.boundary)!=4 or b[2+a]-b[a]+4*EPS < b[3-a]-b[1-a])
    contacts = []
    for i,(a,first) in enumerate(zip(axes,bounds)):
        for j in range(i+1,len(bounds)):
            if j in unscored or i in unscored or axes[j]!=a:
                continue
            second = bounds[j]
            normal = 1-a
            touching = (abs(first[2+normal]-second[normal])<=4*EPS
                        or abs(second[2+normal]-first[normal])<=4*EPS)
            shared = min(first[2+a],second[2+a])-max(first[a],second[a])
            if touching and shared>4*EPS:
                contacts.append((i,j))
    return RegionRecommendation(None if unscored else -2*len(contacts),
                                tuple(contacts),unscored)


def _canonical(ring):
    if area(ring) < 0:
        ring = tuple(reversed(ring))
    return min(ring[i:] + ring[:i] for i in range(len(ring)))


def _intrinsic(fp, point):
    ux, uy = fp.frame.direction
    x = (point[0] - fp.frame.origin[0]) / fp.frame.scale
    y = (point[1] - fp.frame.origin[1]) / fp.frame.scale
    return ux*x + uy*y, -uy*x + ux*y


def propose_regions(fp, outlines, *, source, provenance=None):
    """Accept connected simple orthogonal supports supplied in input/world XY.

    The coordinate arrangement below is ephemeral coverage computation, not a
    semantic atom partition. No hole filling, component splitting, ownership
    priority, residual-area assignment or roof-model inference is performed.
    Provenance refers to the supplied decomposition and never changes support.
    """
    if not fp.orthogonal:
        raise UnsupportedRoofError('region proposal requires an orthogonal footprint')
    if not isinstance(source, str) or not source.strip():
        raise UnsupportedRoofError('region proposal needs an explicit source')
    if provenance is not None and provenance.footprint != fp:
        raise UnsupportedRoofError('region provenance refers to a different footprint')
    rings = []
    for outline in outlines:
        polygon = analyze(outline)  # rejects self-contact, holes and multi-component input
        ring = tuple(_intrinsic(fp, polygon.frame.world_xy(p)) for p in polygon.vertices)
        if any(min(abs(b[0]-a[0]), abs(b[1]-a[1])) > 4*EPS
               for a,b in zip(ring,ring[1:]+ring[:1])):
            raise UnsupportedRoofError('region support is not aligned with footprint axes')
        rings.append(_canonical(ring))
    if not rings:
        raise UnsupportedRoofError('region proposal leaves the footprint uncovered')
    rings.sort()
    cells = ([tuple(provenance.vertices[i] for i in c.corners) for c in provenance.cells]
             if provenance is not None else [])
    outlines = (fp.vertices, *rings, *cells)
    xs, ys = (sorted({p[k] for ring in outlines for p in ring}) for k in (0,1))
    overlaps = [[[] for _ in cells] for _ in rings]
    interiors=tuple(_interior(ring) for ring in rings)
    source_interiors=tuple(_interior(ring) for ring in cells)
    footprint_interior=_interior(fp.vertices)
    # A boundary-aligned arrangement has constant interior ownership in each
    # open rectangle. Round-trip coordinate differences below the existing
    # footprint numerical resolution cannot have a reliable interior probe.
    # This is a perimeter-normalized allowance, not a region-size heuristic.
    for x0,x1 in zip(xs,xs[1:]):
        for y0,y1 in zip(ys,ys[1:]):
            if x1-x0 <= 4*EPS or y1-y0 <= 4*EPS:
                continue
            center = (x0+(x1-x0)/2, y0+(y1-y0)/2)
            owners = [i for i,contains in enumerate(interiors) if contains(center)]
            covered = footprint_interior(center)
            if len(owners)>1:
                raise UnsupportedRoofError('region interiors overlap')
            if owners and not covered:
                raise UnsupportedRoofError('region support extends outside footprint')
            if covered and not owners:
                raise UnsupportedRoofError('region proposal leaves footprint uncovered')
            if owners and cells:
                sources = [i for i,contains in enumerate(source_interiors) if contains(center)]
                if len(sources)!=1:
                    raise UnsupportedRoofError('source Cell provenance does not cover footprint once')
                overlaps[owners[0]][sources[0]].append((x1-x0)*(y1-y0))
    regions = tuple(RoofRegion(ring,tuple(CellOverlap(c.id,math.fsum(overlaps[i][j]))
                    for j,c in enumerate(provenance.cells) if overlaps[i][j]))
                    if provenance is not None else RoofRegion(ring)
                    for i,ring in enumerate(rings))
    identity = point_identity(fp)
    key = tuple(sorted(_canonical(tuple(identity(p) for p in ring)) for ring in rings))
    return RoofRegionCandidate(fp,regions,source,derive(0,'region_geometry',key))


def minimum_regions(decomposition):
    """Minimum Cells are one proposal source, without extra authority."""
    fp = decomposition.footprint
    return propose_regions(fp,
        [tuple(fp.frame.world_xy(decomposition.vertices[i]) for i in c.corners)
         for c in decomposition.cells],
        source='minimum_partition',provenance=decomposition)
