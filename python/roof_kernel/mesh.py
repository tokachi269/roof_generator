# SPDX-License-Identifier: GPL-3.0-or-later
"""Indexed view of completed source patches; no topology repair or tessellation."""
from dataclasses import dataclass
from functools import cmp_to_key
import math
from .boundary import point,sub,dot,cross
from .precision import scalar


class WallRequired(ValueError):
    """A weakly monotone complex needs internal vertical patches."""


class MeshResolutionError(ValueError):
    """The requested floating-point mesh cannot preserve the exact complex."""


@dataclass(frozen=True)
class Mesh:
    vertices: tuple
    faces: tuple
    sources: tuple
    roles: tuple
    source_vertices: tuple


def exterior_wall(complex,wall):
    """Certify a wall's full projected interval lies on the original path.

    Gable supports may extend past their original segment during propagation.
    A stationary patch is not necessarily an exterior gable wall.
    """
    plane=complex.planes[wall.plane]
    direction=plane.direction
    def project(xy):return sum((xy[k]*direction[k] for k in (0,1)),scalar(0))
    values=[project(complex.vertices[i].xy) for i in wall.loop]
    order=cmp_to_key(complex.precision.compare)
    lo,hi=min(values,key=order),max(values,key=order)
    intervals=[]
    for source in complex.boundary.sources:
        a,b=point(source.start),point(source.end)
        local=tuple((a[k]-complex.frame.origin[k])/complex.frame.scale for k in (0,1))
        if dot(plane.normal,local)!=plane.offset or cross(direction,sub(b,a)):continue
        first,second=sorted((dot(direction,a),dot(direction,b)))
        intervals.append((first,second))
    covered=lo
    for a,b in sorted(intervals):
        if complex.precision.compare(b,covered)<=0:continue
        if complex.precision.compare(a,covered)>0:return False
        covered=scalar(b)
        if complex.precision.compare(covered,hi)>=0:return True
    return False


def view(complex,*,pitch=.5,eave_height=0.,include_walls=False):
    if not math.isfinite(pitch) or pitch<=0 or not math.isfinite(eave_height):
        raise ValueError('finite positive pitch and finite eave height required')
    if not include_walls:
        internal=[wall.sources for wall in complex.walls if not exterior_wall(complex,wall)]
        if internal:raise WallRequired('roof-only export would remove required internal wall patches: '+repr(internal))
    patches=complex.patches+complex.walls if include_walls else complex.patches
    used=tuple(sorted({v for patch in patches for v in patch.loop}))
    indices={old:i for i,old in enumerate(used)}
    try:coordinates=complex.coordinates(pitch=pitch,eave_height=eave_height)
    except OverflowError as exc:raise MeshResolutionError('exact coordinates exceed floating-point range') from exc
    vertices=tuple(coordinates[i] for i in used)
    faces=tuple(tuple(indices[v] for v in patch.loop) for patch in patches)
    if any(not math.isfinite(x) for v in vertices for x in v) or len(set(vertices))!=len(vertices):
        raise MeshResolutionError('floating-point coordinates lose distinct exact vertices')
    for face in faces:
        origin=vertices[face[0]]
        points=[tuple(vertices[i][k]-origin[k] for k in (0,1,2)) for i in face]
        normal=tuple(math.fsum(a[(k+1)%3]*b[(k+2)%3]-a[(k+2)%3]*b[(k+1)%3]
                               for a,b in zip(points,points[1:]+points[:1])) for k in (0,1,2))
        if not any(normal):raise MeshResolutionError('floating-point conversion loses a source patch area')
    return Mesh(vertices,faces,tuple(patch.sources for patch in patches),
                tuple(complex.planes[patch.plane].role for patch in patches),used)
