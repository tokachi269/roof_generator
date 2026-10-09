# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-input bounded hybrid existence experiment; timeout remains incomplete."""
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
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--category')
    parser.add_argument('--code-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=15)
    args=parser.parse_args()
    if args.seconds<=0:raise ValueError('positive wall budget required')
    payload=args.inputs.read_bytes()
    if args.inputs.suffix=='.gz':payload=gzip.decompress(payload)
    data=json.loads(payload)
    records=[dict(r,category=args.category) for r in data['corpora'][args.category]] if args.category else data['inputs']
    workers=('hybrid_roofs.py','probe_hybrid_roofs.py')
    hashes={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for name in workers}
    core={p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
          for p in sorted((args.code_root/'addon/roof_generator/core').glob('*.py'))}
    rows=[]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='hybrid-worker-',dir=args.output.parent) as folder:
        source=Path(folder)/'input.json';target=Path(folder)/'result.json'
        for record in records:
            source.write_bytes(json.dumps({'inputs':[record]}).encode())
            target.unlink(missing_ok=True)
            try:
                run=subprocess.run([sys.executable,str(Path(__file__).with_name('probe_hybrid_roofs.py')),
                    '--inputs',str(source),'--code-root',str(args.code_root),'--output',str(target)],
                    capture_output=True,text=True,timeout=args.seconds)
                if run.returncode or not target.exists():raise RuntimeError(run.stderr[-2000:])
                receipt=json.loads(target.read_bytes())
                if receipt['diagnostic_source_files_sha256']!=hashes or receipt['core_source_files_sha256']!=core:
                    raise RuntimeError('source changed during bounded hybrid comparison')
                row=receipt['rows'][0]
            except subprocess.TimeoutExpired:
                row={'name':record['name'],'category':record.get('category','user_images'),
                     'embedded':False,'stage':'search_incomplete','search_complete':False,
                     'error':'per-input wall budget exhausted; no impossibility claim'}
            rows.append(row)
            report={'scope':__doc__,'inputs_sha256':hashlib.sha256(payload).hexdigest(),
                    'diagnostic_source_files_sha256':hashes,'core_source_files_sha256':core,
                    'per_input_seconds':args.seconds,'requested_inputs':len(records),'finished_inputs':len(rows),
                    'embedded_inputs':sum(r['embedded'] for r in rows),
                    'stages':dict(Counter(r['stage'] for r in rows)),'rows':rows}
            args.output.write_bytes((json.dumps(report,indent=2)+'\n').encode())
            if len(rows)%10==0 or len(rows)==len(records):
                print(len(rows),len(records),report['embedded_inputs'],report['stages'],flush=True)


if __name__=='__main__':main()
