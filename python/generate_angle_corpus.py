# SPDX-License-Identifier: GPL-3.0-or-later
"""Frozen arbitrary-angle probes; affine stress is not an equivalence oracle."""
import argparse
import gzip
import json
import math
from pathlib import Path
import random

ROOT=Path(__file__).resolve().parents[1]
SEED=982143


def corpus():
    saved=json.loads(gzip.decompress((ROOT/'python/docs/canonical/coverage_inputs_v1.json.gz').read_bytes()))
    acceptance=json.loads((ROOT/'python/tests/fixtures/roof_acceptance.json').read_text())
    rng=random.Random(SEED)
    categories={}

    def paired(category, records):
        for kind in ('gable','hip'):
            categories[category+'_'+kind]=[dict(r,roof_type=kind) for r in records]

    paired('convex_quad',saved['corpora']['convex_quadrilateral'])
    paired('mixed_angle',saved['corpora']['structured_oblique'])
    paired('general_simple',saved['corpora']['general_simple_polygon_probe'])
    paired('oblique_acceptance',[r for r in acceptance if r['name']=='oblique_L'])
    records=[]
    for i in range(64):
        width=rng.uniform(3,6);length=rng.uniform(12,19);rise=rng.uniform(8,13)
        # Shape names belong only to this test generator. Production sees points.
        forms=(
            [(0,0),(length,0),(length,width),(width,width),(width,rise),(0,rise)],
            [(0,0),(length,0),(length,width),(length*.65,width),(length*.65,rise),
             (length*.4,rise),(length*.4,width),(0,width)],
            [(0,0),(length,0),(length,rise),(length-width,rise),(length-width,width),
             (width,width),(width,rise),(0,rise)],
            [(0,0),(width,0),(width,-rise*.6),(2*width,-rise*.6),(2*width,0),
             (length,0),(length,width),(2*width,width),(2*width,rise),
             (width,rise),(width,width),(0,width)],
        )
        ring=forms[i%len(forms)]
        shear=rng.choice((-1,1))*rng.uniform(.15,.85);stretch=rng.uniform(.75,1.3)
        angle=rng.uniform(-math.pi,math.pi);c,s=math.cos(angle),math.sin(angle)
        points=[]
        for x,y in ring:
            u,v=x+shear*y,stretch*y
            points.append([c*u-s*v+37,s*u+c*v-23])
        records.append({'name':f'two_direction_{i:04d}','footprint':points})
    paired('two_direction',records)
    return {'version':1,'seed':SEED,
            'scope':'separate input families and explicit requested roof types; no overall coverage percentage',
            'affine_scope':'invertible affine stress input, not preserved pitch/width/roof equivalence',
            'corpora':categories}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    payload=(json.dumps(corpus(),separators=(',',':'))+'\n').encode()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(gzip.compress(payload,mtime=0))
    print('Saved',args.output)
