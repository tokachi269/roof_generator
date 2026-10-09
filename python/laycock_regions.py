# SPDX-License-Identifier: GPL-3.0-or-later
"""Diagnostic Laycock section 7, steps 1-5. Never constructs a RoofGraph.

AAR growth and collection priority are unspecified in the paper. Enumerate
maximal interior AARs as a declared probe, and show priority sensitivity rather
than publishing any one interpretation as architectural authority.
"""
import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
from itertools import permutations
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addon'))
from roof_generator.core.footprint import analyze, ray_hit
from roof_generator.core.partition_candidates import candidates
from shapely.geometry import Polygon, LineString, box
from shapely.ops import polygonize, unary_union


def elementary(fp):
    """Full interior horizontal/vertical reflex rays, noded at all crossings."""
    rays = []
    for vertex in fp.reflex:
        for direction in (fp.directions[vertex-1], tuple(-v for v in fp.directions[vertex])):
            hit = ray_hit(fp.vertices, vertex, direction)
            if hit:
                # Orthogonal intersection uses the original boundary's exact
                # constant coordinate, avoiding a one-ulp dangling ray endpoint.
                moving = int(abs(direction[1]) > abs(direction[0]))
                endpoint = list(fp.vertices[vertex])
                endpoint[moving] = fp.vertices[hit[1]][moving]
                rays.append((fp.vertices[vertex],tuple(endpoint)))
    footprint = Polygon(fp.vertices)
    edges = [footprint.boundary] + [LineString(r) for r in rays]
    regions = sorted((p for p in polygonize(unary_union(edges))
                      if footprint.covers(p.representative_point())), key=lambda p:p.bounds)
    assert all(abs(p.area-box(*p.bounds).area) < 1e-7 for p in regions)
    assert abs(sum(p.area for p in regions)-footprint.area) < 1e-7
    assert unary_union(regions).symmetric_difference(footprint).area < 1e-7
    return regions, rays


def maximal_rectangles(points):
    """Enumerate maximal interior rectangles on the boundary-coordinate grid.

    This is an explicit growth probe, not a growth rule claimed from Laycock.
    Prefix occupancy queries avoid a Boolean operation for every candidate.
    """
    footprint = Polygon(points)
    xs, ys = (sorted(set(p[k] for p in points)) for k in (0,1))
    nx, ny = len(xs)-1, len(ys)-1
    prefix = [[0]*(ny+1) for _ in range(nx+1)]
    for i in range(nx):
        for j in range(ny):
            occupied = footprint.contains(box(xs[i],ys[j],xs[i+1],ys[j+1]).centroid)
            prefix[i+1][j+1] = int(occupied)+prefix[i][j+1]+prefix[i+1][j]-prefix[i][j]
    def full(a,b,c,d):
        return prefix[c][d]-prefix[a][d]-prefix[c][b]+prefix[a][b] == (c-a)*(d-b)
    result = []
    for a in range(nx):
        for c in range(a+1,nx+1):
            for b in range(ny):
                for d in range(b+1,ny+1):
                    if not full(a,b,c,d):
                        continue
                    if ((a and full(a-1,b,c,d)) or (b and full(a,b-1,c,d))
                        or (c<nx and full(a,b,c+1,d)) or (d<ny and full(a,b,c,d+1))):
                        continue
                    result.append((xs[a],ys[b],xs[c],ys[d]))
    return result


def cell_compatibility(atoms, groups, decomposition):
    """Whole-Cell ownership is possible only if every atom has a common owner.

    Empty intersections prove splitting is necessary for this collection family.
    Nonempty intersections prove only ownership possibility, not paper priority
    or connected roof regions. No nearest-Cell assignment is used.
    """
    domains = [set(i for i,g in enumerate(groups) if a in g) for a in range(len(atoms))]
    rows = []
    for cell in decomposition.cells:
        poly = Polygon([decomposition.vertices[i] for i in cell.corners])
        ids = [i for i,a in enumerate(atoms) if poly.intersection(a).area > 1e-7]
        intersections = [poly.intersection(atoms[i]).area for i in ids]
        assert abs(sum(intersections)-poly.area)<1e-7
        common = set.intersection(*(domains[i] for i in ids))
        rows.append({'cell':cell.id,'atoms':ids,'intersection_areas':intersections,
                     'atoms_crossing_cell_boundary':[i for i,v in zip(ids,intersections) if abs(v-atoms[i].area)>1e-7],
                     'common_collections':sorted(common),
                     'requires_split':not common and all(domains[i] for i in ids),
                     'uncovered':any(not domains[i] for i in ids)})
    return rows


def difference(groups, order):
    """Explicit ordered collection difference; caller must name the order."""
    taken = set()
    result = []
    for i in order:
        remain = set(groups[i])-taken
        taken.update(groups[i])
        if remain:
            result.append({'collection':i,'atoms':sorted(remain)})
    return result


def rings(poly):
    return [{'exterior':list(p.exterior.coords),'holes':[list(h.coords) for h in p.interiors]}
            for p in (poly.geoms if poly.geom_type=='MultiPolygon' else [poly]) if not p.is_empty]


def priority_orders(groups,compatibility,growth_resolved):
    """Exhaust ordered-difference conventions, without choosing a winner."""
    if any(c['uncovered'] for rows in compatibility for c in rows):
        return {'complete':False,'reason':'collection coverage incomplete'}
    if not growth_resolved or len(groups)>8:
        return {'complete':False,'reason':'growth domains unresolved' if not growth_resolved else 'diagnostic priority budget (8 collections)'}
    found = {}
    for order in permutations(range(len(groups))):
        regions = difference(groups,order)
        signature = tuple(sorted((r['collection'],tuple(r['atoms'])) for r in regions))
        if signature in found:
            continue
        exact = []
        for i,rows in enumerate(compatibility):
            if all(not (set(c['atoms']) & set(g['atoms'])) or set(c['atoms'])<=set(g['atoms'])
                   for c in rows for g in regions):
                exact.append(i)
        found[signature] = {'order':order,'regions':regions,'exact_minimum_partitions':exact}
    return {'complete':True,'distinct_configurations':len(found),
            'exact_configurations':sum(bool(r['exact_minimum_partitions']) for r in found.values()),
            'splitting_configurations':sum(not r['exact_minimum_partitions'] for r in found.values()),
            'configurations':list(found.values())}


def inspect(record):
    from py_straight_skeleton import compute_skeleton
    start = time.perf_counter()
    fp = analyze(record['footprint'])
    atoms, rays = elementary(fp)
    out = {'input':record,'frame':asdict(fp.frame),'frame_outline':fp.vertices,'rays':rays,
           'atoms':[rings(a)[0] for a in atoms], 'atom_areas':[a.area for a in atoms]}
    search = candidates(fp)
    out['minimum_search_complete'] = search.complete
    out['minimum_partitions'] = [d.inspect() for d in search.candidates]
    try:
        # Give the external implementation source-unit intrinsic coordinates,
        # not the core's perimeter-normalized coordinates. No jitter is applied.
        scale = fp.frame.scale
        skeleton = compute_skeleton(exterior=[(x*scale,y*scale) for x,y in fp.vertices], holes=[])
        nodes = [{'xy':(n.position.x/scale,n.position.y/scale),'time':n.time/scale} for n in skeleton.nodes]
        arcs = [(a._skn_id,b._skn_id) for a,b in skeleton.arc_iterator()]
        # Verify the library's planar faces only as a skeleton-completeness
        # oracle. These faces are never adopted as roof faces or features.
        face_cycles = skeleton.get_faces()
        faces = [Polygon([nodes[i]['xy'] for i in f]) for f in face_cycles]
        assert all(p.is_valid and p.area>0 for p in faces), 'invalid skeleton face'
        assert abs(sum(p.area for p in faces)-Polygon(fp.vertices).area)<1e-6, 'skeleton face area mismatch'
        assert unary_union(faces).symmetric_difference(Polygon(fp.vertices)).area<1e-6, 'skeleton coverage mismatch'
        for edge,cycle in enumerate(face_cycles):
            a,b = fp.vertices[edge],fp.vertices[(edge+1)%len(fp.vertices)]
            dx,dy = b[0]-a[0],b[1]-a[1]
            for i in cycle:
                x,y = nodes[i]['xy']
                distance = (dx*(y-a[1])-dy*(x-a[0]))/math.hypot(dx,dy)
                assert abs(distance-nodes[i]['time'])<1e-6, 'skeleton time/support mismatch'
        out.update(skeleton_nodes=nodes,skeleton_arcs=arcs,skeleton_face_coverage_verified=True,
                   skeleton_input_scale=scale,skeleton_times_verified=True)
    except Exception as exc:
        out.update(classification='ambiguous / paper underspecified',
                   diagnostic_owner='skeleton_backend', reason=type(exc).__name__+': '+str(exc))
        return out
    guides, guide_times = [], []
    for a,b in arcs:
        p,q = nodes[a]['xy'],nodes[b]['xy']
        if math.dist(p,q)>1e-7 and (abs(p[0]-q[0])<1e-7 or abs(p[1]-q[1])<1e-7):
            guides.append((p,q))
            guide_times.append((nodes[a]['time'],nodes[b]['time']))
    aars = maximal_rectangles(fp.vertices)
    selected, choices, envelope_choices = set(), [], []
    for (p,q),times in zip(guides,guide_times):
        line = LineString((p,q))
        ids = [i for i,r in enumerate(aars) if box(*r).buffer(1e-8).covers(line)
               and box(*r).contains(line.interpolate(.5,normalized=True))]
        envelope_choices.append([aars[i] for i in ids])
        # Figure-4-consistent interpretation: guide is the AAR centreline.
        # The paper does not state a centred-growth stopping rule. Retain
        # unrestricted domains; do not reinterpret wavefront time as width.
        normal = int(abs(p[0]-q[0]) > abs(p[1]-q[1]))
        ids = [i for i in ids if abs((aars[i][normal]+aars[i][normal+2])/2-p[normal])<1e-7]
        choices.append(ids)
        selected.update(ids)
    remap = {old:new for new,old in enumerate(sorted(selected))}
    choices = [[remap[i] for i in ids] for ids in choices]
    aars = [aars[i] for i in sorted(selected)]
    groups = [tuple(i for i,a in enumerate(atoms) if box(*r).buffer(1e-8).covers(a)) for r in aars]
    out.update(guides=guides,guide_times=guide_times,growth_domains=choices,
               unrestricted_maximal_growth_domains=envelope_choices,aars=aars,collections=groups,
               growth_rule='Figure-4-consistent centred maximal interior AAR; explicit diagnostic interpretation, not a stated stopping rule',
               uncovered_atoms=sorted(set(range(len(atoms)))-set().union(*map(set,groups))))
    compatibility = [cell_compatibility(atoms,groups,d) for d in search.candidates]
    out['minimum_compatibility'] = compatibility
    variants = []
    # Opposite deterministic orders measure an unspecified priority's effect.
    # Neither is selected as the correct interpretation or used in production.
    for label,order in (('large_AAR_area_first',sorted(range(len(groups)),key=lambda i:(-box(*aars[i]).area,i))),
                        ('large_collection_first',sorted(range(len(groups)),key=lambda i:(-len(groups[i]),i))),
                        ('small_collection_first',sorted(range(len(groups)),key=lambda i:(len(groups[i]),i)))):
        result = difference(groups,order)
        for g in result:
            g['region'] = rings(unary_union([atoms[i] for i in g['atoms']]))
            g['minimum_matches'] = []
            ids = set(g['atoms'])
            for rows in compatibility:
                selected_cells = [r['cell'] for r in rows if set(r['atoms']) <= ids]
                partial = [r['cell'] for r in rows if set(r['atoms']) & ids and not set(r['atoms']) <= ids]
                g['minimum_matches'].append({'whole_cells':selected_cells,'partial_cells':partial})
        assert len([a for g in result for a in g['atoms']]) == len(set(a for g in result for a in g['atoms']))
        variants.append({'convention':label,'order':order,'regions':result,
                         'not_paper_resolved':True})
    out['difference_union_variants'] = variants
    out['priority_exhaustion'] = priority_orders(groups,compatibility,
                                               bool(guides) and all(len(c)==1 for c in choices))
    ambiguous = (not guides or any(len(c)!=1 for c in choices) or out['uncovered_atoms']
                 or any(sum(a in g for g in groups)>1 for a in range(len(atoms))))
    out['partition_classification'] = [
        'requires splitting a minimum Cell' if any(r['requires_split'] for r in rows)
        else 'no local splitting obligation established' for rows in compatibility]
    out['classification'] = ('ambiguous / paper underspecified' if ambiguous or not search.complete else
                            'exact union of minimum Cells' if any(not any(r['requires_split'] for r in rows) for rows in compatibility)
                            else 'requires splitting a minimum Cell')
    out['classification_scope'] = 'No final region authority if growth or ownership is ambiguous; partial-Cell witnesses below remain conditional.'
    out['seconds'] = time.perf_counter()-start
    return out


def draw(row,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as Patch
    fig,axes = plt.subplots(2,3,figsize=(15,10))
    outline = tuple(row['frame_outline'])
    frame = row['frame']
    def world(p):
        ux,uy = frame['direction']; x,y=p; ox,oy=frame['origin']; scale=frame['scale']
        return ox+scale*(ux*x-uy*y), oy+scale*(uy*x+ux*y)
    titles = ['Footprint / reflex rays','Elementary rectangles','Skeleton / axis guides',
              'Centred AAR probe (not paper-resolved)','Difference + union: AREA FIRST sensitivity',
              'Minimum Cells / partial-Cell witnesses']
    def paint(ax,coords,color,alpha=.3):
        ax.add_patch(Patch([world(p) for p in coords],facecolor=color,edgecolor=color,alpha=alpha))
    for ax,title in zip(axes.flat,titles):
        ax.plot(*zip(*(world(p) for p in outline+(outline[0],))),color='black',lw=1.5)
        ax.set_aspect('equal'); ax.set_title(title,fontsize=10); ax.autoscale_view()
    for a,b in row['rays']:
        axes.flat[0].plot(*zip(world(a),world(b)),color='#aaa',lw=.8,ls='--')
    palette = plt.get_cmap('tab20')
    for i,a in enumerate(row['atoms']):
        paint(axes.flat[1],a['exterior'],palette(i%20),.4)
        x,y = world(Polygon(a['exterior']).representative_point().coords[0])
        axes.flat[1].text(x,y,str(i),fontsize=7,ha='center')
    for a,b in row.get('skeleton_arcs',[]):
        axes.flat[2].plot(*zip(world(row['skeleton_nodes'][a]['xy']),world(row['skeleton_nodes'][b]['xy'])),color='#aaa',lw=1)
    for p,q in row.get('guides',[]):
        axes.flat[2].plot(*zip(world(p),world(q)),color='#a000b4',lw=2)
    for i,(a,b,c,d) in enumerate(row.get('aars',[])):
        axes.flat[3].add_patch(Patch([world(p) for p in ((a,b),(c,b),(c,d),(a,d))],fill=False,edgecolor=palette(i%20),lw=2))
    if row.get('difference_union_variants'):
        for g in row['difference_union_variants'][0]['regions']:
            for poly in g['region']:
                paint(axes.flat[4],poly['exterior'],palette(g['collection']%20),.4)
    if row['minimum_partitions']:
        d = row['minimum_partitions'][0]
        for c in d['cells']:
            pts = [d['vertices'][i] for i in c['corners']]
            paint(axes.flat[5],pts,'#888',.15)
            x,y = world(Polygon(pts).centroid.coords[0])
            axes.flat[5].text(x,y,'C'+str(c['id']),ha='center')
        if row.get('difference_union_variants'):
            for g in row['difference_union_variants'][0]['regions']:
                if g['minimum_matches'][0]['partial_cells']:
                    for poly in g['region']:
                        axes.flat[5].plot(*zip(*(world(p) for p in poly['exterior'])),color=palette(g['collection']%20),lw=2)
    fig.suptitle(row['input']['name']+' — '+row['classification']+'\nNo roof topology; coloured union is a sensitivity convention, not an accepted architecture',fontsize=12)
    fig.tight_layout()
    fig.savefig(path.with_suffix('.png'),dpi=140)
    svg = path.with_suffix('.svg')
    fig.savefig(svg)
    # Matplotlib path lines contain trailing spaces; keep checked-in SVGs
    # readable and independent of the host newline convention.
    svg.write_bytes(('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n').encode('utf-8'))
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--dependency-root',type=Path,default=ROOT/'python/out/laycock-deps')
    args = p.parse_args()
    sys.path.insert(0,str(args.dependency_root))
    args.output_dir.mkdir(parents=True,exist_ok=True)
    data = json.loads(args.inputs.read_text())
    rows = []
    for record in data['inputs']:
        row = inspect(record)
        rows.append(row)
        draw(row,args.output_dir/record['name'])
        print(record['name'],row['classification'],len(row['atoms']),len(row.get('guides',[])),flush=True)
    out = {'scope':'diagnostic steps 1-5 only; no RoofGraph; unspecified growth/priority tested as declared variants',
           'skeleton_backend':{'package':'py_straight_skeleton','version':importlib.metadata.version('py_straight_skeleton')},
           'dependencies':{name:importlib.metadata.version(name) for name in ('shapely','matplotlib')},
           'input_sha256':hashlib.sha256(args.inputs.read_bytes()).hexdigest(),'cases':rows}
    (args.output_dir/'report.json').write_text(json.dumps(out,indent=2)+'\n')


if __name__=='__main__':
    main()
