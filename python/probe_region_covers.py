# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded coordinate-rectangle covers, before any production proposal policy.

No minimum-Cell authority, owner repair or appearance ranking. Search atoms
are temporary coordinate rectangles; accepted supports are actual polygons.
All complete covers up to the explicit member/work budgets are examined.
Relation-domain filtering only skips combinations already unsupported by the
current grammar. End-state and composition rejection remain separately visible.
"""
import argparse
from collections import Counter
from dataclasses import asdict
from itertools import islice
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addon'))
from roof_generator.core.footprint import analyze,inside
from roof_generator.core.roof_regions import propose_regions
from roof_generator.core.region_architecture import interpret_regions
from roof_generator.core.architecture import resolve
from roof_generator.core.architecture_selection import symmetry_clusters
from roof_generator.core.roof_ends import roof_configurations
from roof_generator.core.topology import compose
from roof_generator.core.errors import UnsupportedRoofError


def covers(fp,max_members,max_work):
    if max_members<1 or max_work<1:
        raise ValueError('positive member and work budgets are required')
    xs,ys=(sorted({p[k] for p in fp.vertices}) for k in (0,1))
    atoms=tuple((i,j) for i in range(len(xs)-1) for j in range(len(ys)-1)
                if inside(((xs[i]+xs[i+1])/2,(ys[j]+ys[j+1])/2),fp.vertices))
    positions={p:i for i,p in enumerate(atoms)}
    available=set(atoms);rectangles=[]
    for a in range(len(xs)-1):
        for b in range(a+1,len(xs)):
            for c in range(len(ys)-1):
                for d in range(c+1,len(ys)):
                    points={(i,j) for i in range(a,b) for j in range(c,d)}
                    if points<=available:
                        mask=sum(1<<positions[p] for p in points)
                        ring=tuple(fp.frame.world_xy(p) for p in
                                   ((xs[a],ys[c]),(xs[b],ys[c]),(xs[b],ys[d]),(xs[a],ys[d])))
                        rectangles.append((mask,ring))
    by_atom=tuple(tuple(r for r in rectangles if r[0]&(1<<i)) for i in range(len(atoms)))
    state={'work':0,'complete':True,'covers':0,'atom_count':len(atoms),'rectangle_count':len(rectangles)}
    def visit(remaining,selected):
        state['work']+=1
        if state['work']>max_work:
            state['complete']=False;return
        if not remaining:
            state['covers']+=1;yield selected;return
        if len(selected)>=max_members:return
        atom=(remaining&-remaining).bit_length()-1
        for mask,ring in by_atom[atom]:
            if not state['complete']:return
            if mask&remaining==mask:
                yield from visit(remaining^mask,selected+(ring,))
    return visit((1<<len(atoms))-1,()),state


def assignments(architecture):
    # Geometric relation options are existing model-domain constraints. They
    # are not a ranking prior and do not assert end or junction validity.
    domains={r.cells:{o.axes for o in r.options if o.kind in
                     ('corner','side_attachment','continuation')} for r in architecture.relations}
    if any(not values for values in domains.values()):return
    chosen=[]
    def visit():
        if len(chosen)==len(architecture.members):
            yield tuple(chosen);return
        i=len(chosen)
        for axis in architecture.members[i].axes:
            chosen.append(axis)
            if all(pair[1]>i or tuple(chosen[j] for j in pair) in values
                   for pair,values in domains.items()):yield from visit()
            chosen.pop()
    yield from visit()


def inspect(record,max_members,max_work):
    fp=analyze(record['footprint']);iterator,state=covers(fp,max_members,max_work)
    failures=Counter();accepted=[];axes_count=0;ends_count=0;graph_count=0;empty_domains=0
    for rings in iterator:
        proposal=propose_regions(fp,rings,source='coordinate_cover_probe')
        architecture=interpret_regions(proposal)
        supported_axes=tuple(assignments(architecture))
        if not supported_axes:empty_domains+=1
        for axes in supported_axes:
            axes_count+=1
            authority=resolve(architecture,axes)
            try:ends=tuple(islice(roof_configurations(authority,symmetry_clusters(authority.analysis())),1025))
            except UnsupportedRoofError as exc:
                failures['ends: '+str(exc)]+=1;continue
            if len(ends)>1024:
                state['complete']=False;state['reason']='end configuration budget exceeded';break
            for end in ends:
                ends_count+=1
                resolved=authority.with_ends(end)
                try:
                    c=compose(resolved);graph_count+=1
                    accepted.append({'proposal':proposal.inspect(),'axes':axes,'ends':asdict(end),
                                     'graph':c.graph.inspect()})
                except UnsupportedRoofError as exc:
                    failures['composition: '+str(exc)]+=1
                    # Keep all end-valid support sets as evidence, not seed
                    # candidates. No candidate is repaired to pass this stage.
                    accepted.append({'proposal':proposal.inspect(),'axes':axes,'ends':asdict(end),
                                     'composition_rejection':str(exc)})
            if not state['complete']:break
        if not state['complete']:break
    return {'name':record['name'],'input':record,'search':state,'max_members':max_members,
            'axis_assignments':axes_count,'end_configurations':ends_count,'graphs':graph_count,
            'covers_without_supported_axis_assignment':empty_domains,
            'failures':dict(failures),'end_valid':accepted,
            'scope':'2D supports/global ends/composition only; no embedding or valid-roof claim'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-members',type=int,default=6);p.add_argument('--max-work',type=int,default=100000)
    p.add_argument('--case',action='append')
    args=p.parse_args();rows=[]
    for record in json.loads(args.inputs.read_text(encoding='utf-8'))['inputs']:
        if args.case and record['name'] not in args.case:continue
        row=inspect(record,args.max_members,args.max_work);rows.append(row)
        print(row['name'],row['search'],row['end_configurations'],'end choices',row['graphs'],'graphs',flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes((json.dumps({'scope':__doc__,'cases':rows},indent=2)+'\n').encode())


if __name__=='__main__':main()
