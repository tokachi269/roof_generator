# SPDX-License-Identifier: GPL-3.0-or-later
"""Ten recorded operator cases; images are sanity checks, never scoring inputs."""

import argparse
from html import escape
import json
from pathlib import Path
import shutil
from PIL import Image, ImageDraw
from authority_diagrams import svg

NAMES = ('rectangle', 'orthogonal_L', 'narrow_corner_T', 'orthogonal_T',
         'orthogonal_U', 'cross', 'many_cell_branch_network', 'unknown_supported',
         'unknown_nonuniform', 'offset_rectangles_wide')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    reports = [json.loads((p / 'report.json').read_text()) for p in (args.before, args.after)]
    indexed = [{r['name']: r for r in report['cases']} for report in reports]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cards, records = [], []
    for name in NAMES:
        before, after = (rows[name] for rows in indexed)
        folder = args.output_dir / name
        folder.mkdir(exist_ok=True)
        for label, source in (('before', args.before), ('after', args.after)):
            shutil.copyfile(source / name / 'meshes.png', folder / (label + '.png'))
        picture = Image.new('RGB', (1000, 375), 'white')
        draw = ImageDraw.Draw(picture)
        for i, label in enumerate(('before', 'after')):
            image = Image.open(folder / (label + '.png'))
            image.thumbnail((500, 350))
            picture.paste(image, (i * 500, 25))
            draw.text((i * 500 + 10, 7), label.upper(), fill='black')
        picture.save(folder / 'comparison.png')
        structure = ''
        if before['status'] == after['status'] == 'supported':
            b, a = before['inspection'], after['inspection']
            assert a['selected_candidate'] == after['candidate']
            assert b['selected_candidate'] == before['candidate']
            assert a['solver_preserved_graph'] and b['solver_preserved_graph']
            (folder / 'structure.svg').write_text(svg(b, a, solved=True), encoding='utf-8')
            structure = f'<img src="{name}/structure.svg" alt="Cells, Parts, resolved decisions, final graph">'
        valleys = []
        for feature in after.get('inspection', {}).get('features', ()):
            if feature['kind'] != 'valley':
                continue
            ends = after['inspection']['resolved_ends']
            choice = next(j for j in ends['joints'] if j['cells'] == feature['relation'])
            valleys.append(dict(feature=feature, joint_choice=choice,
                basis='globally compatible shared/T end choice, then restricted incidence; not proof of a unique architectural roof'))
        records.append(dict(name=name, before=before, after=after, valleys=valleys))
        summary = ', '.join(j['kind'] for j in (after.get('inspection', {}).get('resolved_ends') or {}).get('joints', ()))
        rows = ''.join('<tr><td>' + escape(str(v['feature']['vertices'])) + '</td><td>' +
                       escape(str(v['feature']['relation'])) + '</td><td>' +
                       escape(v['joint_choice']['kind']) + '</td></tr>' for v in valleys)
        states = (after.get('inspection', {}).get('resolved_ends') or {}).get('states', ())
        end_rows = ''.join('<tr>' + ''.join('<td>' + escape(str(value)) + '</td>' for value in
                          (s['end']['member'], s['end']['side'], s['shape'], s['connection'])) + '</tr>' for s in states)
        cards.append(f'<details><summary>{escape(name)}: {before["status"]} → {after["status"]}; {escape(summary)}</summary>'
                     f'<img src="{name}/comparison.png" alt="Before and after installed Blender output">{structure}'
                     '<table><tr><th>valley vertices</th><th>member relation</th><th>resolved choice</th></tr>' + rows +
                     '</table><p>resolved end states</p><table><tr><th>member</th><th>side</th><th>shape obligation</th><th>connection</th></tr>' + end_rows +
                     f'</table><a href="{name}/inspection.json">Recorded operator data</a></details>')
        (folder / 'inspection.json').write_text(json.dumps(records[-1], indent=2) + '\n')
    html = '<!doctype html><html lang="ja"><meta charset="utf-8"><title>Roof end decisions</title>'
    html += '<style>body{font:16px system-ui;max-width:1440px;margin:24px auto;padding:16px}img{max-width:100%}summary{cursor:pointer;padding:16px;background:#eee}details{margin:16px 0}td,th{padding:8px;text-align:left}</style>'
    html += '<h1>端制約と屋根構成の代表10ケース</h1><p>赤 ridge・青 valley・橙 hip。実際のinstalled ZIP operatorが選択したデータと、solve後の図。画像はsanity check用で、候補の採点には使わない。</p>'
    html += '<p>shared/Tの採用は全体の端制約から決定する。これは任意footprintに対する唯一の建築解の証明ではない。unsupportedには最終Graphを表示しない。</p>'
    html += ''.join(cards) + '</html>'
    (args.output_dir / 'index.html').write_text(html, encoding='utf-8')
    (args.output_dir / 'manifest.json').write_text(json.dumps({'archives': [r['archive_sha256'] for r in reports], 'cases': NAMES}, indent=2) + '\n')
    print('ROOF_GALLERY', len(records), 'recorded cases')


if __name__ == '__main__':
    main()
