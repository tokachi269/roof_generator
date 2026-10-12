# SPDX-License-Identifier: GPL-3.0-or-later
"""Run frozen construction/counterexample proofs; never claim general coverage."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from python.roof_kernel_proof import construct, export, from_record, nonexistence_witness, ProofDomainError


def run(records,output,*,samples=9):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for index,record in enumerate(records):
        path,intent=from_record(record)
        row={'name':record['name'],'footprint_valid':True,'intent':asdict(intent),
             'input_class':'independent construction proof; not production corpus coverage'}
        if record['proof']=='nonexistence':
            certificate=nonexistence_witness(path,intent,record['witness'])
            if certificate is None:raise AssertionError('nonexistence certificate disappeared')
            row.update(status='inconsistent intent',certificate=certificate)
        else:
            try:
                result=construct(path,intent)
            except ProofDomainError as exc:
                if record['proof']!='unresolved':raise
                row.update(status='outside independent proof domain',reason=str(exc),
                           intent_admissibility='not decided by this tool')
            else:
                if record['proof']!='construction':raise AssertionError('proof scope changed')
                timings=[]
                for _ in range(samples):
                    start=time.perf_counter();repeated=construct(path,intent)
                    timings.append((time.perf_counter()-start)*1000)
                    if repeated!=result:raise AssertionError('nondeterministic construction')
                export(result,output/f'{index:02d}.json')
                row.update(status='convex construction proof',vertices=len(result.vertices),
                           patches=len(result.patches),event_clusters=asdict(result)['events'],
                           work=result.work,median_ms=statistics.median(timings),samples_ms=timings)
        rows.append(row)
    report={'version':1,'method':'convex space-time body enumeration, independent proof only',
            'runtime_adoption':False,'records':rows}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus',type=Path,default=ROOT/'python/tests/fixtures/kernel_line_proofs_v1.json')
    parser.add_argument('--output',type=Path,default=ROOT/'python/out/kernel-proof')
    args=parser.parse_args()
    corpus=json.loads(args.corpus.read_text())
    if corpus['version']!=1:raise ValueError('unknown proof corpus version')
    report=run(corpus['records'],args.output)
    for row in report['records']:
        print(row['name'],row['status'],row.get('median_ms',''))


if __name__=='__main__':main()
