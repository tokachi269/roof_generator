# SPDX-License-Identifier: GPL-3.0-or-later
"""Check saved nonlinear polygon meshes against fixed incident-plane embedding."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addon'))
from roof_generator.core.graph import make_graph, RoofFace
from roof_generator.core.provenance import BoundaryPoint
from roof_generator.core.solve import problem
from roof_generator.core.plane_embedding import embed_planes
from roof_generator.core.mesh import RoofMesh


def graph_from_record(d):
    return make_graph(
        tuple(map(tuple, d['outline'])), tuple(map(tuple, d['source_edges'])),
        tuple(tuple(v['seed']) for v in d['vertices']),
        {i: BoundaryPoint(v['boundary']['edge'], v['boundary']['t'])
         for i, v in enumerate(d['vertices']) if v['boundary']},
        tuple(v['role'] for v in d['vertices']),
        tuple(RoofFace(tuple(f['loop']), tuple(f['cells']), tuple(f['eaves']), f.get('support'))
              for f in d['faces']),
        {tuple(e['vertices']): e['kind'] for e in d['edges']}, d['roof_type'],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = ROOT / 'python/docs/authority/whole-polygon'
    result = {'scope': '995 historical successful meshes; not latest runtime coverage',
              'inputs': {}, 'cases': {}, 'max_vertex_distance': 0., 'failures': []}
    counts = Counter()
    for name in ('grid', 'nonuniform', 'structured', 'images'):
        path = root / ('whole-polygon-split-' + name + '.json.gz')
        payload = gzip.decompress(path.read_bytes())
        result['inputs'][path.name] = hashlib.sha256(payload).hexdigest()
        for row in json.loads(payload)['rows']:
            if not row.get('embedded'):
                continue
            try:
                graph = graph_from_record(row['graph'])
                vertices = embed_planes(problem(graph))
                RoofMesh(graph, vertices)
                if len(vertices) != len(row['vertices']):
                    raise ValueError('vertex ownership changed')
                error = max(math.dist(a, b) for a, b in zip(vertices, row['vertices']))
                result['max_vertex_distance'] = max(result['max_vertex_distance'], error)
                if error > 1e-8:
                    raise ValueError('nonlinear witness differs by ' + str(error))
                if tuple(map(tuple, row['faces'])) != tuple(f.loop for f in graph.faces):
                    raise ValueError('face cycles changed')
                counts[name] += 1
            except Exception as exc:
                result['failures'].append({'corpus': name, 'name': row['name'], 'reason': str(exc)})
    result['cases'] = dict(counts)
    expected = {'grid': 741, 'nonuniform': 149, 'structured': 101, 'images': 4}
    if dict(counts) != expected:
        result['failures'].append({'reason': 'historical witness coverage differs from 995 saved successes',
                                   'expected': expected, 'actual': dict(counts)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(result['cases'], result['max_vertex_distance'], len(result['failures']))
    if result['failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
