# SPDX-License-Identifier: GPL-3.0-or-later
"""Audit the recursive proposal funnel, independently of default seed selection."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addon'))
from roof_generator.core.footprint import analyze
from roof_generator.core.recursive_regions import recursive_regions
from roof_generator.core.region_generation import region_candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--category')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    payload = args.inputs.read_bytes()
    data = json.loads(gzip.decompress(payload) if args.inputs.suffix == '.gz' else payload)
    records = data['corpora'][args.category] if args.category else data['inputs']
    rows = []
    for index, record in enumerate(records):
        search = recursive_regions(analyze(record['footprint']))
        row = {'name': record['name'], 'decomposition_complete': search.complete,
               'decomposition_reason': search.reason, 'proposal_count': len(search.proposals),
               'architecture_complete': None, 'embedded_count': 0, 'selectable': False,
               'rejections_by_stage': {}, 'rejection_reasons': {}}
        if search.complete and search.proposals:
            pool = region_candidates(search.proposals)
            row.update(architecture_complete=pool.complete, architecture_reason=pool.reason,
                       embedded_count=len(pool.valid), selectable=bool(pool.selectable()),
                       rejections_by_stage=dict(Counter(r.stage for r in pool.rejected)),
                       rejection_reasons=dict(Counter((r.stage+': '+r.reason) for r in pool.rejected)))
        rows.append(row)
        if (index+1) % 10 == 0:
            print(index+1, len(records), sum(r['selectable'] for r in rows), flush=True)
    report = {'scope': 'Recursive polygons through all-axis models, global ends, whole graph and embedding; not default generation or Blender coverage',
              'inputs': len(rows), 'selectable_inputs': sum(r['selectable'] for r in rows),
              'decomposition_incomplete': sum(not r['decomposition_complete'] for r in rows),
              'architecture_incomplete': sum(r['architecture_complete'] is False for r in rows),
              'rows': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(report, indent=2)+'\n').encode())
    print({k:v for k,v in report.items() if k != 'rows'}, flush=True)


if __name__ == '__main__':
    main()
