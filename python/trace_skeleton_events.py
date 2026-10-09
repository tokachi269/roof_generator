# SPDX-License-Identifier: GPL-3.0-or-later
"""Reproduce raw skeleton events before any roof conversion or optimization."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys


def load(path):
    payload = path.read_bytes()
    return json.loads(gzip.decompress(payload) if path.suffix == '.gz' else payload)


def trace(fp, skeleton):
    points = [(v.position.x / fp.frame.scale, v.position.y / fp.frame.scale)
              for v in skeleton.nodes]
    loops = [tuple(f[:-1]) for f in skeleton.get_faces()]
    n = len(fp.vertices)
    def height(edge, point):
        a, b = fp.vertices[edge], fp.vertices[(edge + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        return (-dy * (point[0] - a[0]) + dx * (point[1] - a[1])) / math.hypot(dx, dy)
    events = []
    for cap in loops:
        if len(cap) != 3 or cap[2] < n:
            continue
        a, b, node = cap
        incident = [f for f in loops if node in f]
        supports = [f[0] for f in incident]
        raw = [height(e, points[node]) for e in supports]
        midpoint = tuple((fp.vertices[a][k] + fp.vertices[b][k]) / 2 for k in (0, 1))
        moved = [height(e, midpoint) for e in supports if e != a]
        sectors = [{'support':f[0], 'before':f[f.index(node)-1],
                    'after':f[(f.index(node)+1) % len(f)], 'loop':f} for f in incident]
        events.append({'cap_edge':a, 'node':node, 'raw_xy':points[node],
                       'raw_time':skeleton.nodes[node].time / fp.frame.scale,
                       'incident_supports':supports, 'sectors':sectors,
                       'raw_source_heights':raw, 'raw_height_spread':max(raw)-min(raw),
                       'midpoint_xy':midpoint, 'moved_source_heights':moved,
                       'moved_height_spread':max(moved)-min(moved) if moved else None})
        # Independent local delayed-front witness, not a global weighted
        # skeleton implementation. An orthogonal convex cap with stationary
        # support is shortened by its two moving neighboring fronts.
        pa,pb=fp.vertices[a],fp.vertices[b]
        width=math.dist(pa,pb);collapse=width/2
        tangent=tuple((pb[k]-pa[k])/width for k in (0,1))
        samples=[]
        for fraction in (0.,.25,.5,.75,1.):
            t=collapse*fraction
            ends=[tuple(pa[k]+t*tangent[k] for k in (0,1)),
                  tuple(pb[k]-t*tangent[k] for k in (0,1))]
            samples.append({'time':t,'stationary_cap_endpoints':ends})
        extra=[e for e in supports if e not in (a,(a-1)%n,(a+1)%n)]
        events[-1]['local_delayed_cap']={
            'scope':'closed-form terminal corridor only; no global weighted skeleton coverage claim',
            'delay':width,'collapse_time':collapse,'samples':samples,
            'collapse_midpoint_error':math.dist(samples[-1]['stationary_cap_endpoints'][0],midpoint),
            'preserved_event_time_error':abs(skeleton.nodes[node].time/fp.frame.scale-collapse),
            'adjacent_height_error_at_midpoint':max(abs(height(e,midpoint)-collapse)
                                                   for e in ((a-1)%n,(a+1)%n)),
            'additional_support_clearance_at_midpoint':{str(e):height(e,midpoint)-collapse for e in extra}}
    raw_spread = max((max(h)-min(h) for v in range(len(points))
                      if (h := [height(f[0], points[v]) for f in loops if v in f])), default=0)
    return {'nodes':points, 'faces':loops, 'caps':events,
            'raw_max_source_height_spread':raw_spread}


def exception_trace(exc, deps):
    frames = []
    tb = exc.__traceback__
    while tb:
        frame = tb.tb_frame
        path = Path(frame.f_code.co_filename)
        try:
            filename = path.resolve().relative_to(deps.resolve()).as_posix()
        except ValueError:
            filename = path.name
        item = {'file':filename, 'function':frame.f_code.co_name, 'line':tb.tb_lineno}
        if frame.f_code.co_name == 'compute_from_edges':
            for key in ('in_edge','out_edge','in_segment','out_segment','bisector_pos','bisector_neg'):
                value = frame.f_locals.get(key)
                if value is not None:
                    item[key] = [value.x, value.y]
            for key in ('is_in_pos','is_in_neg','is_original_vertex'):
                item[key] = frame.f_locals.get(key)
            vertex = frame.f_locals.get('self')
            item['event_xy'] = [vertex.position.x, vertex.position.y]
            for key in ('prev_orig_edge','next_orig_edge'):
                edge = getattr(vertex, key)
                item[key] = [[v.position.x, v.position.y]
                             for v in (edge.start_vertex,edge.end_vertex)]
        frames.append(item)
        tb = tb.tb_next
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root',type=Path,required=True)
    parser.add_argument('--deps',type=Path,required=True)
    parser.add_argument('--small-inputs',type=Path,required=True)
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--reports',type=Path,nargs='+',required=True)
    parser.add_argument('--categories',nargs='+',required=True,
                        help='explicit category for each report; use per-row for mixed reports')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if len(args.categories) != len(args.reports):
        parser.error('one explicit category per report required')
    sys.path.insert(0,str(args.code_root/'addon'))
    sys.path.insert(0,str(args.deps))
    from roof_generator.core.footprint import analyze
    from py_straight_skeleton import compute_skeleton, __version__
    records = {(r['category'],r['name']):r for r in load(args.small_inputs)['inputs']}
    for category, values in load(args.corpus)['corpora'].items():
        records.update({(category,r['name']):r for r in values})
    rows = []
    for report, category in zip(args.reports,args.categories):
        for previous in load(report)['rows']:
            error = previous.get('error','').lower()
            if previous['stage'] != 'embedding' and not any(s in error for s in ('opposite edges','antiparallel')):
                continue
            key = (previous.get('category',category),previous['name'])
            fp = analyze(records[key]['footprint'])
            row = {'category':key[0],'name':key[1],'previous_stage':previous['stage']}
            try:
                raw = compute_skeleton(exterior=[(x*fp.frame.scale,y*fp.frame.scale)
                                                for x,y in fp.vertices], holes=[])
                row.update(stage='raw_skeleton', trace=trace(fp,raw))
            except Exception as exc:
                row.update(stage='external_skeleton', error=type(exc).__name__+': '+str(exc),
                           frames=exception_trace(exc,args.deps))
            rows.append(row)
    result = {'scope':__doc__, 'dependency_version':__version__,
              'diagnostic_sha256':hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
              'stages':dict(Counter(r['stage'] for r in rows)), 'rows':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(result['stages'])


if __name__ == '__main__':
    main()
