# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded per-input prototype isolation; timeout is censored, not unsupported."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root',type=Path,required=True)
    parser.add_argument('--deps',type=Path,required=True)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--category',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--resume',type=Path)
    parser.add_argument('--seconds',type=float,default=15)
    args=parser.parse_args()
    if args.seconds<=0:raise ValueError('positive per-input budget required')
    payload=args.inputs.read_bytes()
    if args.inputs.suffix=='.gz':payload=gzip.decompress(payload)
    records=json.loads(payload)['corpora'][args.category]
    worker=Path(__file__).with_name('whole_polygon_roofs.py')
    digest=hashlib.sha256(worker.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    corpus_digest=hashlib.sha256(payload).hexdigest()
    hashes={p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
            for p in sorted((args.code_root/'addon/roof_generator/core').glob('*.py'))}
    rows=[]
    if args.resume:
        previous=json.loads(args.resume.read_bytes())
        if (previous['inputs_sha256']!=corpus_digest or previous['diagnostic_sha256']!=digest
            or previous['core_source_files_sha256']!=hashes):
            raise ValueError('resume source or corpus differs from prototype')
        rows=previous['rows']
        if [r['name'] for r in rows]!=[r['name'] for r in records[:len(rows)]]:
            raise ValueError('resume rows are not the exact corpus prefix')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    def checkpoint():
        report={'scope':__doc__,'diagnostic_sha256':digest,'inputs_sha256':corpus_digest,
                'core_source_files_sha256':hashes,'category':args.category,
                'per_input_seconds':args.seconds,'requested_inputs':len(records),
                'finished_inputs':len(rows),'embedded_inputs':sum(r['embedded'] for r in rows),
                'censored_inputs':sum(r['stage']=='search_incomplete' for r in rows),
                'stages':dict(Counter(r['stage'] for r in rows)),'rows':rows}
        args.output.write_bytes((json.dumps(report,indent=2)+'\n').encode())
        return report
    with tempfile.TemporaryDirectory(prefix='whole-polygon-worker-',dir=args.output.parent) as folder:
        source=Path(folder)/'input.json';target=Path(folder)/'result.json'
        for record in records[len(rows):]:
            source.write_bytes(json.dumps({'inputs':[dict(record,category=args.category)]}).encode())
            target.unlink(missing_ok=True)
            try:
                run=subprocess.run([sys.executable,str(worker),
                    '--code-root',str(args.code_root),'--deps',str(args.deps),
                    '--inputs',str(source),'--output',str(target)],
                    capture_output=True,text=True,timeout=args.seconds)
                if run.returncode or not target.exists():
                    raise RuntimeError('isolated worker failed: '+run.stderr[-2000:])
                receipt=json.loads(target.read_bytes())
                if receipt['diagnostic_sha256']!=digest or receipt['core_source_files_sha256']!=hashes:
                    raise RuntimeError('worker source changed during comparison')
                row=receipt['rows'][0]
            except subprocess.TimeoutExpired:
                row={'name':record['name'],'category':args.category,'embedded':False,
                     'stage':'search_incomplete','error':'per-input wall budget exhausted; no impossibility claim'}
            rows.append(row)
            report=checkpoint()
            if len(rows)%10==0 or len(rows)==len(records):
                print(len(rows),len(records),report['embedded_inputs'],report['censored_inputs'],flush=True)


if __name__=='__main__':main()
