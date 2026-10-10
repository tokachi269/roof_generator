# SPDX-License-Identifier: GPL-3.0-or-later
"""Same-source-family embedding latency, fixed candidates and optional cProfile."""

import argparse
import cProfile
from dataclasses import asdict
import functools
import gzip
import json
from pathlib import Path
import platform
import pstats
import subprocess
import sys
import time
from contextlib import contextmanager

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--code-root', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--samples', type=int, default=5)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--profile', action='store_true')
args = parser.parse_args()
if args.samples < 1:
    parser.error('--samples must be positive')
root = args.code_root.resolve()
sys.path[:0] = [str(root / 'addon'), str(Path(__file__).resolve().parent)]
from roof_generator.core import polygon_generation as pg, solve as geometry
from roof_generator.core.footprint import analyze
from roof_generator.core.generation import GenerationSettings
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.core.mesh import RoofMesh
from inspect_architectural_parts import fixture
from measurements import stats


@contextmanager
def stage_probe():
    originals, stack, stages = [], [], {}

    def wrap(owner, name, label):
        original = getattr(owner, name)

        @functools.wraps(original)
        def measured(*a, **kw):
            item = [time.perf_counter(), 0.0]
            stack.append(item)
            try:
                return original(*a, **kw)
            finally:
                elapsed = time.perf_counter() - item[0]
                stack.pop()
                if stack:
                    stack[-1][1] += elapsed
                row = stages.setdefault(label, {'calls': 0, 'inclusive_ms': 0., 'exclusive_ms': 0.})
                row['calls'] += 1
                row['inclusive_ms'] += elapsed * 1000
                row['exclusive_ms'] += (elapsed - item[1]) * 1000

        originals.append((owner, name, original))
        setattr(owner, name, measured)

    for owner, name, label in (
        (pg, 'wavefront', 'topology_incidence'),
        (pg, 'receiver_regions', 'receiver_guides'),
        (pg, 'decompose', 'minimum_partition'),
        (pg, 'recommend', 'end_recommendation'),
        (pg, 'topology', 'roof_graph'),
        (pg, 'problem', 'geometry_problem'),
        (pg, 'check_planes', 'plane_feasibility'),
        (geometry, 'embed', 'embedding'),
        (RoofMesh, '__post_init__', 'mesh_validation'),
    ):
        wrap(owner, name, label)
    try:
        yield stages
    finally:
        for owner, name, original in reversed(originals):
            setattr(owner, name, original)


def run(raw):
    return pg.candidates(analyze(raw), GenerationSettings())


def snapshot(pool):
    return {
        'complete': pool.complete, 'reason': pool.reason, 'work': pool.work,
        'models': [m.inspect() for m in pool.interpretation.models],
        'rejected': [asdict(r) for r in pool.rejected],
        'constructible': [c.id for c in pool.constructible],
        'valid': [{'id': c.id, 'graph': c.graph.inspect(), 'geometry': asdict(c.geometry),
                   'vertices': c.mesh.vertices} for c in pool.valid],
        'seed_ids': [pool.select(s).id for s in (0, 1, 7, 42)] if pool.complete and pool.valid else [],
    }


output = {
    'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip()),
    'python': platform.python_version(), 'platform': platform.platform(),
    'unprofiled_latency': True, 'persistent_cache': False,
    'stage_scope': 'one separate instrumented sample; inclusive stages contain their children',
    'cases': {},
}
for name in ('orthogonal_L', 'orthogonal_T', 'orthogonal_U', 'cross', 'residential_multi_reflex',
             'grid_14', 'grid_20', 'grid_40'):
    raw = fixture(name)['footprint']
    times = []
    try:
        for i in range(args.samples + 1):
            started = time.perf_counter()
            pool = run(raw)
            if i:
                times.append((time.perf_counter() - started) * 1000)
        with stage_probe() as stages:
            pool = run(raw)
        output['cases'][name] = {'footprint': raw, 'latency': stats(times), 'stages': stages,
                                 'snapshot': snapshot(pool)}
    except UnsupportedRoofError as exc:
        output['cases'][name] = {'footprint': raw, 'unsupported': str(exc)}
    row = output['cases'][name]
    print(name, row.get('unsupported') or round(row['latency']['median_ms'], 3), flush=True)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_bytes(gzip.compress((json.dumps(output, separators=(',', ':')) + '\n').encode(), mtime=0))
if args.profile:
    profiler = cProfile.Profile()
    profiler.runcall(run, fixture('grid_20')['footprint'])
    with args.output.with_suffix('.profile.txt').open('w') as f:
        pstats.Stats(profiler, stream=f).sort_stats('cumtime').print_stats(40)
