# SPDX-License-Identifier: GPL-3.0-or-later
"""Recover producer alternatives from a completed pinned baseline audit.

Read failed minimum assignments directly; do not reconstruct RoofGraphs for
them. Re-evaluate only their geometric contact options. The small receiver
family and successful inputs are checked through the pinned public pipeline.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys

from causal_roof_audit import source_frontier, STAGE_ORDER


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root',type=Path,required=True)
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--details',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--output-details',type=Path,required=True)
    args=parser.parse_args()
    metadata=json.loads(args.report.read_bytes())
    if metadata['axis_ablation']:
        raise ValueError('this replay requires the unchanged-axis baseline')
    payload=gzip.decompress(args.corpus.read_bytes())
    if hashlib.sha256(payload).hexdigest()!=metadata['corpus_sha256']:
        raise ValueError('replay corpus differs from audited corpus')
    records={(category,r['name']):r for category,rows in json.loads(payload)['corpora'].items() for r in rows}
    sys.path.insert(0,str(args.code_root/'addon'))
    from roof_generator.core.footprint import analyze
    from roof_generator.core.partition_candidates import candidates
    from roof_generator.core.architecture import analyze_parts
    from roof_generator.core.architecture_selection import recommend
    from roof_generator.core.topology_candidates import partition_id
    from roof_generator.core.roof_candidates import roof_candidates
    from roof_generator.core.receiver_regions import receiver_regions
    from roof_generator.core.region_architecture import interpret_receiver
    from roof_generator.core.region_generation import region_candidates, RegionPool
    from roof_generator.core.generation import GenerationSettings
    from roof_generator.core.errors import UnsupportedRoofError

    summary={'source_sha':metadata['source_sha'],'scope':__doc__,
             'input_details_sha256':hashlib.sha256(args.details.read_bytes()).hexdigest(),
             'corpora':{}}
    buckets={}
    args.output_details.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(args.details,'rt',encoding='utf-8') as stream, gzip.open(args.output_details,'wt',encoding='utf-8') as output:
        for index,line in enumerate(stream):
            row=json.loads(line);category=row['category']
            fp=analyze(records[category,row['name']]['footprint'])
            search=candidates(fp)
            analyses={partition_id(d):analyze_parts(d) for d in search.candidates}
            stages={}
            # Older audit receipts copied a receiver embedding rejection into
            # the minimum list via the combined public rejection pool. Match
            # its explicit original receiver receipt, not an unknown ID guess.
            receiver_embeddings={(r['geometry'],tuple(r['axes']),r['reason'])
                                 for r in row['candidates']
                                 if r['source']=='receiver' and r['reached_stage']=='embedding'}
            for failure in row['candidates']:
                if failure['source']!='minimum' or not failure['axes']:
                    continue
                if (failure['reached_stage']=='embedding' and
                    (failure['geometry'],tuple(failure['axes']),failure['reason']) in receiver_embeddings):
                    continue
                key=(failure['geometry'],tuple(failure['axes']))
                stage=failure['reached_stage']
                if STAGE_ORDER.get(stage,0)>=STAGE_ORDER.get(stages.get(key,'model'),0):
                    stages[key]=stage
            if row['embedded']:
                # Sparse successful inputs also need their successful modeled
                # assignments; the rejection log alone cannot establish them.
                pool=roof_candidates(fp,recommend(search,defer_ranking=True),GenerationSettings())
                embedded={identity for identity,mesh in pool.meshes}
                for candidate in pool.minimum.constructible:
                    stages[partition_id(candidate.architecture.decomposition),candidate.axes]='mesh' if candidate.id in embedded else 'embedding'
            minimum=[]
            for (identity,axes),stage in stages.items():
                analysis=analyses[identity]
                if len(axes)!=len(analysis.members):
                    raise RuntimeError('recorded axes do not cover the audited minimum models')
                kinds=[]
                for relation in analysis.relations:
                    assignment=tuple(axes[c] for c in relation.cells)
                    options=[o for o in relation.options if o.axes==assignment]
                    if len(options)!=1:
                        raise RuntimeError('recorded axes fail unique geometric contact binding')
                    kinds.append(options[0].kind)
                minimum.append(('parallel' in kinds,stage))
            reason=row['incomplete_reason'] or ''
            minimum_complete=search.complete and not reason.startswith(('topology axis-assignment','roof end-configuration'))
            receiver=receiver_regions(fp)
            regional=region_candidates(receiver.proposals,model=interpret_receiver) if receiver.proposals else RegionPool((),(),True)
            modeled={};model_failures=0
            for proposal in regional.proposals:
                if proposal.id in modeled:
                    continue
                try:modeled[proposal.id]=interpret_receiver(proposal)
                except UnsupportedRoofError:model_failures+=1
            region_stages={}
            for rejection in regional.rejected:
                if not rejection.axes or rejection.region_id not in modeled:
                    continue
                key=(rejection.region_id,rejection.axes)
                if STAGE_ORDER.get(rejection.stage,0)>=STAGE_ORDER.get(region_stages.get(key,'model'),0):
                    region_stages[key]=rejection.stage
            for candidate in regional.valid:
                region_stages[candidate.architecture.layout.candidate.id,candidate.axes]='mesh'
            region_observations=[]
            for (identity,axes),stage in region_stages.items():
                architecture=modeled[identity]
                kinds=[next(o.kind for o in r.options if o.axes==tuple(axes[c] for c in r.cells)) for r in architecture.relations]
                region_observations.append(('parallel' in kinds,stage))
            sources={'minimum':source_frontier(minimum,minimum_complete),
                     'receiver':source_frontier(region_observations,receiver.complete and regional.complete,model_failures)}
            replay={'category':category,'name':row['name'],'complete':row['complete'],
                    'producer_parallel_frontiers':sources}
            output.write(json.dumps(replay,separators=(',',':'))+'\n')
            bucket=buckets.setdefault(category,{'counts':Counter(),'states':{s:Counter() for s in sources},'free_stages':{s:Counter() for s in sources},'combined':Counter()})
            bucket['counts']['inputs']+=1
            for source,details in sources.items():
                bucket['states'][source][details['state']]+=1
                if details['complete'] and details['parallel_free_assignments']:
                    bucket['free_stages'][source][details['parallel_free_max_reached_stage']]+=1
            free=[s['parallel_free_max_reached_stage'] for s in sources.values() if s['parallel_free_assignments']]
            state='search_incomplete' if not row['complete'] else 'parallel_free_reaches_'+max(free,key=lambda s:STAGE_ORDER.get(s,0)) if free else 'no_parallel_free_modeled_candidate'
            bucket['combined'][state]+=1
            if sources['minimum']['state']=='parallel_unavoidable_in_modeled_family' and sources['receiver']['state']=='parallel_free_candidate':
                bucket['counts']['receiver_parallel_free_when_minimum_unavoidable']+=1
                bucket['counts']['receiver_mesh_when_minimum_unavoidable']+=sources['receiver']['parallel_free_mesh_assignments']>0
            if (index+1)%25==0:
                print(index+1,category,dict(bucket['counts']),flush=True)
    for category,bucket in buckets.items():
        summary['corpora'][category]={'counts':dict(bucket['counts']),
            'producer_parallel_states':{s:dict(v) for s,v in bucket['states'].items()},
            'producer_parallel_free_max_stage':{s:dict(v) for s,v in bucket['free_stages'].items()},
            'combined_states':dict(bucket['combined'])}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes((json.dumps(summary,indent=2)+'\n').encode())


if __name__=='__main__':main()
