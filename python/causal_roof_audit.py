# SPDX-License-Identifier: GPL-3.0-or-later
"""Pinned-generator, building-level observed failure frontiers and axis ablation.

Rejections censor downstream stages. A minimal observed set is a necessary
repair opportunity, never a promise that implementing its labels rescues a roof.
"""
import argparse
from collections import Counter
from dataclasses import asdict, replace
from contextlib import ExitStack
import gzip
import hashlib
import inspect
import json
from pathlib import Path
import sys
import textwrap
from unittest.mock import patch


def minimal_sets(sets):
    unique = {frozenset(s) for s in sets if s}
    return sorted((sorted(s) for s in unique if not any(t < s for t in unique)),
                  key=lambda s: (len(s), s))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--category', action='append')
    parser.add_argument('--all-axis', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--details', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_root / 'addon'))
    from roof_generator.core import architecture as ar
    from roof_generator.core import architecture_selection as selection
    from roof_generator.core.footprint import analyze, EPS
    from roof_generator.core.partition_candidates import candidates
    from roof_generator.core.roof_candidates import roof_candidates
    from roof_generator.core.topology_candidates import partition_id
    from roof_generator.core.generation import GenerationSettings
    from roof_generator.core import architecture_models
    from roof_generator.core.region_architecture import interpret_receiver
    from roof_generator.core.errors import UnsupportedRoofError
    candidate_module = sys.modules['roof_generator.core.roof_candidates']
    receiver_original = candidate_module.receiver_regions
    receiver_receipts = []
    def observe_receiver(*arguments, **keywords):
        result = receiver_original(*arguments, **keywords)
        receiver_receipts.append(result)
        return result

    original = selection.analyze_parts
    def both_axes(d):
        analysis = original(d)
        models = tuple(replace(m, axes=(0,1)) for m in analysis.members)
        return ar.Analysis(models, ar.relation_options(d.vertices,d.cells,
            tuple((a.cells,a.sides,a.interval) for a in d.adjacency), models))

    # The same long-axis domain is enforced by the immutable record validator.
    # Replace only that exact assertion in this diagnostic process. Retain all
    # other bounds, coverage, provenance, relation and grouping validation.
    validator = architecture_models.ArchitecturalPartGraph.__post_init__
    if args.all_axis:
        source = textwrap.dedent(inspect.getsource(validator))
        old = '''        elif m.axes != axes:
            raise UnsupportedRoofError(
                "member axes differ from its geometric domain"
            )'''
        new = '''        elif not m.axes or any(a not in (0, 1) for a in m.axes):
            raise UnsupportedRoofError("invalid diagnostic axis domain")'''
        if source.count(old) != 1:
            raise RuntimeError('pinned validator axis assertion changed; stop ablation')
        namespace = {}
        exec(compile(source.replace(old,new),'<diagnostic-axis-validator>','exec'),
             dict(vars(architecture_models)),namespace)
        validator = namespace['__post_init__']

    order = {'model':0,'relation':1,'ends':2,'architecture':2,'junction':3,
             'composition':3,'geometry_problem':4,'graph_validation':4,'embedding':5,'mesh':6}
    def labels(issues):
        return sorted({i.code.removeprefix('inter_part_').removeprefix('internal_')
                       if i.code != 'unsupported' else i.stage for i in issues})

    def parallel_shapes(interpretation, minimum, statuses):
        shapes = Counter()
        by_partition = {partition_id(a.decomposition):a for _,a in interpretation.retained}
        assignments = {(r.partition,r.axes) for r in minimum.rejected}
        assignments.update((c.partition,c.axes) for c in minimum.architectural)
        for identity, axes in assignments:
            source = by_partition.get(identity)
            if source is None or len(axes) != len(source.members):
                continue
            resolved = ar.resolve(source,axes)
            layout = resolved.layout
            statuses[identity,axes] = any(r.options[0].kind == 'parallel' for r in resolved.relations)
            for relation in resolved.relations:
                if relation.options[0].kind != 'parallel':
                    continue
                a,b = relation.cells
                bounds = [resolved.architecture.members[i].bounds for i in (a,b)]
                axis = axes[a]
                widths = [v[3-axis]-v[1-axis] for v in bounds]
                equal = abs(widths[0]-widths[1]) <= 4*EPS
                aligned = all(abs(bounds[0][i]-bounds[1][i])<=4*EPS for i in (axis,axis+2))
                centered = abs(sum(bounds[0][i] for i in (axis,axis+2))-
                               sum(bounds[1][i] for i in (axis,axis+2))) <= 8*EPS
                full = []
                nodes = {v for interval in relation.intervals for v in interval}
                contact = sorted(layout.vertices[v][axis] for v in nodes)
                for member,side in zip(relation.cells,relation.sides):
                    span = sorted(layout.vertices[v][axis] for v in layout.supports[member].sides[side].vertices)
                    full.append(abs(span[0]-contact[0])<=4*EPS and abs(span[1]-contact[-1])<=4*EPS)
                shape = ('equal_width' if equal else 'unequal_width')+'/'
                shape += 'aligned' if aligned else 'centered' if centered else 'offset'
                shape += '/'+('both_full' if all(full) else 'one_full' if any(full) else 'both_partial')
                shape += '/'+('same_part' if resolved.internal(relation) else 'between_parts')
                shapes[shape] += 1
        return shapes

    def source_frontier(observations, complete, model_failures=0):
        free = [stage for parallel,stage in observations if not parallel]
        return {'complete':complete, 'modeled_assignments':len(observations),
                'model_failures':model_failures,
                'parallel_free_assignments':len(free),
                'parallel_free_mesh_assignments':sum(s=='mesh' for s in free),
                'parallel_free_max_reached_stage':max(free,key=lambda s:order.get(s,0),default=None),
                'state':'incomplete' if not complete else 'no_modeled_candidate' if not observations
                        else 'parallel_free_candidate' if free else 'parallel_unavoidable_in_modeled_family',
                'scope':'actual declared contact options before end consumption; later stages may be censored'}

    def producer_frontiers(pool, statuses, receiver_complete):
        minimum = {}
        embedded_ids={identity for identity,mesh in pool.meshes}
        for r in pool.minimum.rejected:
            stage=max((i.stage for i in r.issues),key=lambda s:order.get(s,0),default='composition')
            key=(r.partition,r.axes)
            if key in statuses and order.get(stage,0)>=order.get(minimum.get(key,'model'),0):
                minimum[key]=stage
        for c in pool.minimum.constructible:
            key=(partition_id(c.architecture.decomposition),c.axes)
            minimum[key]='mesh' if c.id in embedded_ids else 'embedding'
        minimum_report=source_frontier([(statuses[k],s) for k,s in minimum.items() if k in statuses],pool.minimum.complete)
        regional={};architectures={};model_failures=0
        for proposal in pool.regions.proposals:
            if proposal.id in architectures:
                continue
            try:architectures[proposal.id]=interpret_receiver(proposal)
            except UnsupportedRoofError:
                # Only absence of an applicable model; never infer an axis or
                # count this as a parallel-free architectural interpretation.
                model_failures+=1
        for r in pool.regions.rejected:
            if not r.axes or r.region_id not in architectures:
                continue
            key=(r.region_id,r.axes)
            if order.get(r.stage,0)>=order.get(regional.get(key,'model'),0):
                regional[key]=r.stage
        for c in pool.regions.valid:
            regional[c.architecture.layout.candidate.id,c.axes]='mesh'
        observations=[]
        for (identity,axes),stage in regional.items():
            resolved=ar.resolve(architectures[identity],axes)
            observations.append((any(r.options[0].kind=='parallel' for r in resolved.relations),stage))
        return {'minimum':minimum_report,
                'receiver':source_frontier(observations,pool.regions.complete and receiver_complete,model_failures),
                'recursive':{'state':'not_in_pinned_default_family','scope':'requires separate proposal/grammar diagnostic'}}

    payload = gzip.decompress(args.corpus.read_bytes())
    data = json.loads(payload)
    summary = {'source_sha':args.source_sha,'axis_ablation':args.all_axis,
               'diagnostic_sha256':hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
               'only_changed_constraint':'minimum rectangular member axes=(0,1)' if args.all_axis else None,
               'corpus_sha256':hashlib.sha256(payload).hexdigest(),
               'frontier_scope':'inclusion-minimal observed first-failure sets; downstream censored, not sufficient rescue conditions',
               'corpora':{}}
    args.details.parent.mkdir(parents=True,exist_ok=True)
    with ExitStack() as stack:
        stack.enter_context(patch.object(selection,'analyze_parts',both_axes if args.all_axis else original))
        stack.enter_context(patch.object(candidate_module,'receiver_regions',observe_receiver))
        if args.all_axis:
            stack.enter_context(patch.object(architecture_models.ArchitecturalPartGraph,'__post_init__',validator))
        stream = stack.enter_context(gzip.open(args.details,'wt',encoding='utf-8'))
        for category,records in data['corpora'].items():
            if args.category and category not in args.category:
                continue
            counts = Counter(); frontiers = Counter(); stages = Counter(); shapes = Counter()
            producer_states={source:Counter() for source in ('minimum','receiver')}
            producer_stages={source:Counter() for source in ('minimum','receiver')}
            for index, record in enumerate(records):
                fp=analyze(record['footprint']);search=candidates(fp)
                interpretation=selection.recommend(search,defer_ranking=True)
                receiver_receipts.clear()
                pool=roof_candidates(fp,interpretation,GenerationSettings())
                failures=[]
                for rejection in pool.minimum.rejected:
                    failures.append({'source':'minimum','geometry':rejection.partition,
                        'axes':rejection.axes,'end_choices':rejection.end_choices,
                        'blockers':labels(rejection.issues),'issues':[asdict(i) for i in rejection.issues],
                        'reached_stage':max((i.stage for i in rejection.issues),key=lambda s:order.get(s,0),default='composition'),
                        'reason':rejection.reason})
                for rejection in pool.regions.rejected:
                    failures.append({'source':'receiver','geometry':rejection.region_id,
                        'axes':rejection.axes,'blockers':[rejection.stage],
                        'reached_stage':rejection.stage,'reason':rejection.reason})
                for rejection in pool.rejected:
                    if any(i.stage=='embedding' for i in rejection.issues):
                        failures.append({'source':'minimum','geometry':rejection.partition,
                            'axes':rejection.axes,'blockers':['embedding'],
                            'reached_stage':'embedding','reason':rejection.reason})
                frontier=minimal_sets(r['blockers'] for r in failures)
                embedded=bool(pool.meshes);selectable=pool.complete and bool(pool.valid)
                reached='embedding' if embedded else max((r['reached_stage'] for r in failures),key=lambda s:order.get(s,0),default='model')
                statuses={}
                shape_counts=parallel_shapes(interpretation,pool.minimum,statuses)
                sources=producer_frontiers(pool,statuses,receiver_receipts[0].complete)
                row={'name':record['name'],'category':category,'complete':pool.complete,
                     'incomplete_reason':pool.reason if not pool.complete else None,
                     'selectable':selectable,'embedded':embedded,'max_reached_stage':reached,
                     'minimal_observed_blocker_sets':frontier,'candidates':failures,
                     'parallel_shapes':dict(shape_counts),'producer_parallel_frontiers':sources}
                stream.write(json.dumps(row,separators=(',',':'))+'\n')
                counts['inputs']+=1;counts['selectable']+=selectable;counts['incomplete']+=not pool.complete
                stages[reached]+=1
                if pool.complete and not selectable:
                    frontiers.update('+'.join(s) for s in frontier)
                shapes.update(shape_counts.keys())
                for source in producer_states:
                    producer_states[source][sources[source]['state']]+=1
                    if sources[source]['complete'] and sources[source]['parallel_free_assignments']:
                        producer_stages[source][sources[source]['parallel_free_max_reached_stage']]+=1
                if (sources['minimum']['state']=='parallel_unavoidable_in_modeled_family'
                    and sources['receiver']['state']=='parallel_free_candidate'):
                    counts['receiver_parallel_free_when_minimum_unavoidable']+=1
                    counts['receiver_mesh_when_minimum_unavoidable']+=sources['receiver']['parallel_free_mesh_assignments']>0
                if (index+1)%25==0:
                    print(category,index+1,len(records),dict(counts),flush=True)
            summary['corpora'][category]={'counts':dict(counts),'max_reached_stage':dict(stages),
                'minimal_observed_sets_building_incidence_nonexclusive':dict(frontiers),
                'parallel_shape_building_incidence_nonexclusive':dict(shapes),
                'producer_parallel_states':{s:dict(v) for s,v in producer_states.items()},
                'producer_parallel_free_max_stage':{s:dict(v) for s,v in producer_stages.items()}}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes((json.dumps(summary,indent=2)+'\n').encode())


if __name__=='__main__':
    main()
