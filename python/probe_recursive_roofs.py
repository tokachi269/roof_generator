# SPDX-License-Identifier: GPL-3.0-or-later
"""Audit the recursive proposal funnel, independently of default seed selection."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys

from causal_roof_audit import source_frontier, STAGE_ORDER


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--category')
    parser.add_argument('--code-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source-sha', default='working-tree')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_root / 'addon'))
    from roof_generator.core.footprint import analyze
    from roof_generator.core.recursive_regions import recursive_regions
    from roof_generator.core.region_generation import region_candidates
    from roof_generator.core.region_architecture import interpret_regions
    from roof_generator.core.errors import UnsupportedRoofError
    payload = args.inputs.read_bytes()
    data = json.loads(gzip.decompress(payload) if args.inputs.suffix == '.gz' else payload)
    records = data['corpora'][args.category] if args.category else data['inputs']
    rows = []
    for index, record in enumerate(records):
        search = recursive_regions(analyze(record['footprint']))
        row = {'name': record['name'], 'decomposition_complete': search.complete,
               'decomposition_reason': search.reason, 'proposal_count': len(search.proposals),
               'architecture_complete': None, 'embedded_count': 0, 'selectable': False,
               'rejections_by_stage': {}, 'rejection_reasons': {},
               'producer_parallel_frontier': source_frontier([], search.complete)}
        if search.complete and search.proposals:
            pool = region_candidates(search.proposals)
            row.update(architecture_complete=pool.complete, architecture_reason=pool.reason,
                       embedded_count=len(pool.valid), selectable=bool(pool.selectable()),
                       rejections_by_stage=dict(Counter(r.stage for r in pool.rejected)),
                       rejection_reasons=dict(Counter((r.stage+': '+r.reason) for r in pool.rejected)))
            architectures = {}; model_failures = 0
            for proposal in pool.proposals:
                if proposal.id in architectures:
                    continue
                try:
                    architectures[proposal.id] = interpret_regions(proposal)
                except UnsupportedRoofError:
                    model_failures += 1
            stages = {}
            for rejection in pool.rejected:
                if not rejection.axes or rejection.region_id not in architectures:
                    continue
                key = (rejection.region_id, rejection.axes)
                if STAGE_ORDER.get(rejection.stage, 0) >= STAGE_ORDER.get(stages.get(key, 'model'), 0):
                    stages[key] = rejection.stage
            for candidate in pool.valid:
                stages[candidate.architecture.layout.candidate.id, candidate.axes] = 'mesh'
            observations = []
            for (identity, axes), stage in stages.items():
                kinds = []
                for relation in architectures[identity].relations:
                    options = [o for o in relation.options if o.axes == tuple(axes[c] for c in relation.cells)]
                    if len(options) != 1:
                        raise RuntimeError('recursive model axes lack unique geometric contact binding')
                    kinds.append(options[0].kind)
                observations.append(('parallel' in kinds, stage))
            row['producer_parallel_frontier'] = source_frontier(observations, pool.complete, model_failures)
        rows.append(row)
        if (index+1) % 10 == 0:
            print(index+1, len(records), sum(r['selectable'] for r in rows), flush=True)
        report = {'scope': 'Recursive polygons through all-axis models, global ends, whole graph and embedding; not default generation or Blender coverage',
              'source_sha': args.source_sha,
              'corpus_sha256': hashlib.sha256(gzip.decompress(payload) if args.inputs.suffix == '.gz' else payload).hexdigest(),
              'source_files_sha256': {p.name: hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                                     for p in sorted((args.code_root / 'addon/roof_generator/core').glob('*.py'))},
              'requested_inputs': len(records), 'inputs': len(rows),
              'selectable_inputs': sum(r['selectable'] for r in rows),
              'decomposition_incomplete': sum(not r['decomposition_complete'] for r in rows),
              'architecture_incomplete': sum(r['architecture_complete'] is False for r in rows),
              'producer_parallel_states': dict(Counter(r['producer_parallel_frontier']['state'] for r in rows)),
              'parallel_free_max_stage': dict(Counter(r['producer_parallel_frontier']['parallel_free_max_reached_stage']
                    for r in rows if r['producer_parallel_frontier']['complete'] and r['producer_parallel_frontier']['parallel_free_assignments'])),
              'rows': rows}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes((json.dumps(report, indent=2)+'\n').encode())
    print({k:v for k,v in report.items() if k != 'rows'}, flush=True)


if __name__ == '__main__':
    main()
