# SPDX-License-Identifier: GPL-3.0-or-later
"""Audit saved aggregation alternatives in 2D; never validates roof topology."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from shapely.geometry import Polygon, box
from shapely.ops import unary_union


def audit(report):
    rows = []
    for case in report['cases']:
        exhaustive = case['priority_exhaustion']
        if not exhaustive['complete']:
            rows.append({'name': case['input']['name'], 'complete': False,
                         'reason': exhaustive['reason']})
            continue
        # Collection labels and priority orders are not geometric identity.
        configurations = {tuple(sorted(tuple(g['atoms']) for g in c['regions']))
                          for c in exhaustive['configurations']}
        atoms = [Polygon(a['exterior'], a['holes']) for a in case['atoms']]
        footprint = Polygon(case['frame_outline'])
        disconnected = nonrectangular = holes = 0
        for key in configurations:
            assert sorted(a for group in key for a in group) == list(range(len(atoms)))
            regions = [unary_union([atoms[i] for i in group]) for group in key]
            assert all(p.is_valid for p in regions)
            assert abs(sum(p.area for p in regions) - footprint.area) < 1e-7
            assert unary_union(regions).symmetric_difference(footprint).area < 1e-7
            disconnected += any(p.geom_type != 'Polygon' for p in regions)
            nonrectangular += any(abs(p.area - box(*p.bounds).area) > 1e-7 for p in regions)
            holes += any(any(part.interiors for part in
                             (p.geoms if p.geom_type == 'MultiPolygon' else (p,)))
                         for p in regions)
        rows.append({'name': case['input']['name'], 'complete': True,
                     'labelled_configurations': exhaustive['distinct_configurations'],
                     'region_set_configurations': len(configurations),
                     'disconnected_configurations': disconnected,
                     'nonrectangular_configurations': nonrectangular,
                     'configurations_with_holes': holes,
                     'roof_validity': 'not evaluated'})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.report.read_bytes()
    report = json.loads(gzip.decompress(raw) if args.report.suffix == '.gz' else raw)
    result = {'scope': '2D coverage and order/collection-label deduplication only; no roof-valid classification',
              'input_report_sha256': hashlib.sha256(raw).hexdigest(), 'cases': audit(report)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(result, indent=2) + '\n').encode('utf-8'))
    print('Audited', len(result['cases']), 'saved cases; no RoofGraph constructed.')


if __name__ == '__main__':
    main()
