# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent convex space-time roof proof, not the production wavefront engine.

Full Line sources with declared EAVE/GABLE roles define a bounded convex body in
(x,y,time). Enumerating its vertices verifies event/source incidence without an
ordinary skeleton, a cap rewrite, a polygon overlay or an embedding optimizer.
This oracle intentionally has no concave/partial/curve construction path.
"""
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from itertools import combinations
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import python
from roof_generator.core.footprint import analyze, inside

TOL = 2e-9  # Perimeter-normalized proof tolerance, not an exact-predicate claim.


class ProofDomainError(ValueError):
    """The independent convex proof does not certify this input class."""


class ProofBudget(RuntimeError):
    """No incomplete vertex/patch prefix may be returned."""


@dataclass(frozen=True)
class Line:
    id: str
    start: tuple[float, float]
    end: tuple[float, float]

    def evaluate(self, t):
        if not 0 <= t <= 1:
            raise ValueError('source parameter outside [0,1]')
        return tuple(a + t * (b-a) for a,b in zip(self.start,self.end))


@dataclass(frozen=True)
class BoundaryPath:
    sources: tuple[Line, ...]

    def __post_init__(self):
        if len(self.sources) < 3 or any(not isinstance(s,Line) for s in self.sources):
            raise ValueError('closed Line source path required by this proof')
        if any(not s.id or not isinstance(s.id,str) for s in self.sources) or \
           len({s.id for s in self.sources}) != len(self.sources):
            raise ValueError('unique nonempty caller source IDs required')
        if any(a.end != b.start for a,b in zip(self.sources,self.sources[1:]+self.sources[:1])):
            raise ValueError('source path is not continuous and closed')
        # Boundary validity only. Do not use normalized/snap/collinear-removal
        # output as our source path or discard an intent transition.
        analyze(self.outline)

    @property
    def outline(self):
        return tuple(s.start for s in self.sources)


@dataclass(frozen=True)
class RoofIntent:
    roles: tuple[tuple[str, str], ...]

    def bind(self, path):
        mapping=dict(self.roles)
        if len(mapping)!=len(self.roles) or set(mapping)!={s.id for s in path.sources} \
           or any(role not in ('EAVE','GABLE') for role in mapping.values()):
            raise ValueError('full source role coverage required')
        if 'EAVE' not in mapping.values():
            raise ValueError('no inclined source: all-gable intent cannot close a roof')
        return mapping


@dataclass(frozen=True)
class Vertex:
    xy: tuple[float, float]
    time: float
    sources: tuple[str, ...]


@dataclass(frozen=True)
class Patch:
    source: str
    interval: tuple[float, float]
    loop: tuple[int, ...]


@dataclass(frozen=True)
class Contact:
    vertex: int
    sources: tuple[str, ...]


@dataclass(frozen=True)
class EventCluster:
    time: float
    contacts: tuple[Contact, ...]


@dataclass(frozen=True)
class RoofComplex:
    boundary: BoundaryPath
    intent: RoofIntent
    vertices: tuple[Vertex, ...]
    patches: tuple[Patch, ...]
    events: tuple[EventCluster, ...]
    work: int

    def coordinates(self, *, pitch=.5, eave_height=0.):
        if not math.isfinite(pitch) or pitch<=0 or not math.isfinite(eave_height):
            raise ValueError('positive finite pitch and finite eave height required')
        return tuple((*v.xy,eave_height+pitch*v.time) for v in self.vertices)


def _cross(a,b):
    return a[0]*b[1]-a[1]*b[0]


def _dot(a,b):
    return sum(x*y for x,y in zip(a,b))


def _det(rows):
    a,b,c=rows
    return a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])


def _intersection(rows, constants):
    det=_det(rows)
    if abs(det)<1e-12:
        # Numerically singular triples are not treated as exact certificates.
        # Other triples can describe their shared vertex. Validation below is
        # necessary; this float oracle supplies no universal robustness claim.
        return None
    return tuple(_det(tuple(tuple(constants[i] if j==k else rows[i][j] for j in range(3))
                           for i in range(3)))/det for k in range(3))


def _supports(path):
    origin=path.outline[0]
    scale=sum(math.dist(s.start,s.end) for s in path.sources)
    xy=tuple(((p[0]-origin[0])/scale,(p[1]-origin[1])/scale) for p in path.outline)
    forward=sum(_cross(a,b) for a,b in zip(xy,xy[1:]+xy[:1]))>0
    normals=[]
    for source in path.sources:
        dx,dy=(source.end[i]-source.start[i] for i in (0,1))
        size=math.hypot(dx,dy)
        n=(-dy/size,dx/size) if forward else (dy/size,-dx/size)
        a=tuple((source.start[i]-origin[i])/scale for i in (0,1))
        normals.append((source.id,n,_dot(n,a)))
    return origin,scale,xy,tuple(normals)


def nonexistence_witness(path,intent,point):
    """A point below every eave plane is a necessary-condition counterexample.

    Returning None is not a proof of admissibility or of wavefront completion.
    """
    roles=intent.bind(path)
    origin,scale,ring,supports=_supports(path)
    q=tuple((point[k]-origin[k])/scale for k in (0,1))
    if not inside(q,ring):
        raise ValueError('strictly interior witness point required')
    distances={sid:scale*(_dot(n,q)-c) for sid,n,c in supports if roles[sid]=='EAVE'}
    if max(distances.values()) < -TOL*scale:
        return {'point':tuple(point),'inward_distances':distances,
                'reason':'every available eave plane is below the common eave height'}
    return None


def construct(path,intent,*,max_work=100000):
    """Enumerate a convex space-time body; no iterative wavefront is claimed."""
    if isinstance(max_work,bool) or not isinstance(max_work,int) or max_work<1:
        raise ValueError('positive proof work budget required')
    roles=intent.bind(path)
    origin,scale,ring,supports=_supports(path)
    for i,a in enumerate(ring):
        b=ring[(i+1)%len(ring)]
        sid,n,c=supports[i]
        if any(_dot(n,p)-c < -TOL for p in ring):
            raise ProofDomainError('concave path is outside the convex construction proof')
        previous=ring[i-1]
        if abs(_cross((a[0]-previous[0],a[1]-previous[1]),(b[0]-a[0],b[1]-a[1]))) < TOL*TOL:
            raise ProofDomainError('collinear role/source transition requires its own model rule')
    # All constraints have row dot (x,y,t) >= constant. Eaves move at 1;
    # gables remain at 0; the last constraint is the t=0 base, not a roof face.
    rows=tuple((n[0],n[1],-float(roles[sid]=='EAVE')) for sid,n,c in supports)+((0.,0.,1.),)
    constants=tuple(c for sid,n,c in supports)+(0.,)
    points=[]
    work=0
    for triple in combinations(range(len(rows)),3):
        work+=1
        if work>max_work:
            raise ProofBudget('space-time enumeration incomplete')
        p=_intersection(tuple(rows[i] for i in triple),tuple(constants[i] for i in triple))
        if p is None or any(_dot(row,p)<c-TOL for row,c in zip(rows,constants)):
            continue
        if not any(math.dist(p,q)<=TOL*4 for q in points):
            points.append(p)
    points.sort(key=lambda p:(p[2],p[0],p[1]))
    source_sets=[tuple(sorted(sid for sid,row,c in zip((s.id for s in path.sources),rows,constants)
                             if abs(_dot(row,p)-c)<=TOL*4)) for p in points]
    patches=[]
    for source in sorted(path.sources,key=lambda s:s.id):
        if roles[source.id]!='EAVE':continue
        indices=[i for i,owners in enumerate(source_sets) if source.id in owners]
        if len(indices)<3:
            raise RuntimeError('convex proof lost an inclined source facet')
        center=tuple(sum(points[i][k] for i in indices)/len(indices) for k in (0,1))
        loop=tuple(sorted(indices,key=lambda i:math.atan2(points[i][1]-center[1],points[i][0]-center[0])))
        patches.append(Patch(source.id,(0.,1.),loop))
    used=sorted({i for patch in patches for i in patch.loop})
    reindex={old:new for new,old in enumerate(used)}
    vertices=tuple(Vertex(tuple(origin[k]+points[i][k]*scale for k in (0,1)),
                          max(0.,points[i][2])*scale,source_sets[i]) for i in used)
    patches=tuple(Patch(p.source,p.interval,tuple(reindex[i] for i in p.loop)) for p in patches)
    contacts=[]
    for i,v in enumerate(vertices):
        if v.time>TOL*scale:contacts.append(Contact(i,v.sources))
    groups=[]
    for contact in sorted(contacts,key=lambda c:(vertices[c.vertex].time,c.sources)):
        time=vertices[contact.vertex].time
        if not groups or abs(time-groups[-1][0])>TOL*scale*4:
            groups.append((time,[contact]))
        else:groups[-1][1].append(contact)
    result=RoofComplex(path,intent,vertices,patches,
                       tuple(EventCluster(t,tuple(cs)) for t,cs in groups),work)
    _validate(result)
    return result


def _validate(result):
    """Local algebra and incidence only; tests use independent coverage oracles."""
    incidence=defaultdict(list)
    for f,patch in enumerate(result.patches):
        if len(patch.loop)<3 or len(set(patch.loop))!=len(patch.loop):
            raise RuntimeError('proof facet has an invalid cycle')
        for a,b in zip(patch.loop,patch.loop[1:]+patch.loop[:1]):
            incidence[tuple(sorted((a,b)))].append((a,b,f))
    boundary=defaultdict(set)
    for entries in incidence.values():
        if len(entries)==1:
            a,b,_=entries[0];boundary[a].add(b);boundary[b].add(a)
        elif len(entries)!=2 or entries[0][:2]!=entries[1][:2][::-1]:
            raise RuntimeError('proof facet incidence is not an oriented manifold')
    if any(len(v)!=2 for v in boundary.values()):
        raise RuntimeError('proof boundary has a branching vertex')
    seen=set();pending=[next(iter(boundary))]
    while pending:
        node=pending.pop()
        if node not in seen:seen.add(node);pending.extend(boundary[node]-seen)
    if len(seen)!=len(boundary) or len(result.vertices)-len(incidence)+len(result.patches)!=1:
        raise RuntimeError('proof roof is not a topological disk')


def from_record(record):
    points=tuple(tuple(float(v) for v in p) for p in record['footprint'])
    ids=tuple(record.get('source_ids',[f'edge{i}' for i in range(len(points))]))
    if len(ids)!=len(points):raise ValueError('one source ID per input line required')
    path=BoundaryPath(tuple(Line(sid,a,b) for sid,a,b in zip(ids,points,points[1:]+points[:1])))
    intent=RoofIntent(tuple(zip(ids,record['roles'])))
    return path,intent


def export(result,output,*,pitch=.5,eave_height=0.):
    """Display discretization of an already constructed planar proof complex."""
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(asdict(result),indent=2)+'\n')
    coordinates=result.coordinates(pitch=pitch,eave_height=eave_height)
    obj=['# Independent convex roof proof; not a production kernel']
    obj.extend('v '+' '.join(format(x,'.17g') for x in p) for p in coordinates)
    obj.extend('f '+' '.join(str(i+1) for i in p.loop) for p in result.patches)
    output.with_suffix('.obj').write_text('\n'.join(obj)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-work',type=int,default=100000)
    args=parser.parse_args()
    path,intent=from_record(json.loads(args.input.read_text()))
    result=construct(path,intent,max_work=args.max_work)
    export(result,args.output)
    print(json.dumps({'status':'convex construction proof','vertices':len(result.vertices),
                      'patches':len(result.patches),'clusters':len(result.events),'work':result.work}))


if __name__=='__main__':main()
