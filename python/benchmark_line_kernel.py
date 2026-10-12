# SPDX-License-Identifier: GPL-3.0-or-later
"""Unprofiled construction samples plus separate exclusive stage observations."""
import argparse
from collections import defaultdict
from contextlib import ExitStack
import cProfile
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from python.audit_line_kernel import record_model
from python.roof_kernel import wavefront,validation
from python.roof_kernel.mesh import view


def fingerprint(result):
    record=result.inspect();record.pop('predicates');record.pop('work')
    return hashlib.sha256(json.dumps(record,sort_keys=True,default=str).encode()).hexdigest()


def stages(record):
    elapsed=defaultdict(float);stack=[]
    def wrap(function,name):
        def call(*args,**kwargs):
            start=time.perf_counter();entry=[0.];stack.append(entry)
            try:return function(*args,**kwargs)
            finally:
                dt=time.perf_counter()-start;stack.pop();elapsed[name]+=dt-entry[0]
                if stack:stack[-1][0]+=dt
        return call
    path,intent=record_model(record)
    with ExitStack() as context:
        for method,name in (('__init__','intent_sources'),('next_time','certificates'),('nodes','noding'),
                            ('split','noding'),('strip','swept_strips'),('resolve','contact_link')):
            context.enter_context(patch.object(wavefront.Wavefront,method,wrap(getattr(wavefront.Wavefront,method),name)))
        for owner,method,name in ((wavefront,'patch_cycles','patch_cycles'),(wavefront,'compact','seam_compaction'),
                                  (validation,'validate','validation')):
            context.enter_context(patch.object(owner,method,wrap(getattr(owner,method),name)))
        begin=time.perf_counter();result=wavefront.construct(path,intent);total=time.perf_counter()-begin
    elapsed['remaining']=total-sum(elapsed.values())
    return {key:value*1000 for key,value in elapsed.items()},fingerprint(result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples',type=int,default=9)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--profile',action='store_true')
    args=parser.parse_args()
    if args.samples<1:parser.error('positive samples required')
    records=json.loads((ROOT/'python/tests/fixtures/kernel_line_construction.json').read_text())['records']
    rows=[]
    for record in records:
        path,intent=record_model(record)
        expected=wavefront.construct(path,intent);signature=fingerprint(expected)
        construction=[];meshing=[]
        for _ in range(args.samples):
            start=time.perf_counter();result=wavefront.construct(path,intent);construction.append((time.perf_counter()-start)*1000)
            assert fingerprint(result)==signature
            start=time.perf_counter();mesh=view(result,include_walls=record.get('include_walls',False));meshing.append((time.perf_counter()-start)*1000)
        observations,checked=stages(record);assert checked==signature
        rows.append({'name':record['name'],'corners':len(path.sources),'events':len(expected.events),
                     'construction_median_ms':statistics.median(construction),'construction_samples_ms':construction,
                     'mesh_median_ms':statistics.median(meshing),'mesh_samples_ms':meshing,
                     'stages_ms':observations,'fingerprint':signature,'work':expected.work,
                     'predicates':expected.precision.inspect()})
        print(record['name'],rows[-1]['construction_median_ms'],flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    report={'scope':'explicit full-edge intent; no architectural search or nonlinear solve',
            'timing':'unprofiled warm samples; exclusive stage timings are separate instrumented observations',
            'cases':rows}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    if args.profile:
        record=next(r for r in records if r['name']=='grid_40')
        profiler=cProfile.Profile();profiler.runcall(wavefront.construct,*record_model(record))
        profiler.dump_stats(str(args.output.with_suffix('.pstats')))


if __name__=='__main__':main()
