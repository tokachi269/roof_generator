# SPDX-License-Identifier: GPL-3.0-or-later
"""Check local documentation links and lossless evidence relocation."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def main():
    names = subprocess.check_output(
        ['git', 'ls-files', '--', '*.md'], cwd=ROOT, text=True
    ).splitlines()
    documents = {ROOT / name for name in names}
    documents.update((ROOT / 'python/docs').rglob('*.md'))
    errors = []
    links = 0
    for document in sorted(documents):
        if not document.exists():
            continue
        text = document.read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)\n]+)\)', text):
            if re.match(r'(?:[A-Za-z][\w+.-]*:|#|/)', target):
                continue
            path = unquote(target.split('#', 1)[0])
            if not path:
                continue
            links += 1
            if not (document.parent / path).exists():
                errors.append(f'{document.relative_to(ROOT)}: missing {path}')
    catalog = json.loads((ROOT / 'python/docs/evidence/catalog.json').read_text())
    records = catalog['artifacts'] + catalog['extracted_partition_inputs']
    for record in records:
        path = ROOT / record['path']
        if not path.is_file():
            errors.append(f'missing evidence: {record["path"]}')
        elif hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            errors.append(f'evidence content changed: {record["path"]}')
    original = {r['original']: ROOT / r['path'] for r in catalog['artifacts']}
    for record in catalog['extracted_partition_inputs']:
        source = json.loads(original[record['derived_from']].read_text())['input']
        extracted = json.loads((ROOT / record['path']).read_text())['input']
        if source != extracted:
            errors.append(f'partition input changed: {record["path"]}')
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'Documentation: {links} local links; {len(records)} evidence/input hashes; '
          'extracted partition inputs match their frozen sources')


if __name__ == '__main__':
    main()
