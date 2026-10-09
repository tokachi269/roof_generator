# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only paired diagrams of recorded historical and installed polygon roofs."""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addon'))
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    old = {r['input']['name']: r for r in json.loads(args.before.read_text())['cases']}
    rows = [r for r in json.loads(args.after.read_text())['cases'] if r['name'] in old]
    colors = {'ridge': '#be243b', 'valley': '#1665be', 'hip': '#b37712',
              'eave': '#565f67', 'gable_end': '#565f67'}
    figure, panels = plt.subplots(len(rows), 4, figsize=(20, 5 * len(rows)), squeeze=False)
    for line, row in enumerate(rows):
        data = row['inspection']; graph = data['graph']; raw = data['input']['footprint']
        source = graph['source_edges'][0][0]
        a, b = graph['outline'][:2]; p, q = raw[source], raw[(source + 1) % len(raw)]
        dx, dy = b[0] - a[0], b[1] - a[1]; wx, wy = q[0] - p[0], q[1] - p[1]
        length = dx * dx + dy * dy
        c, s = (wx * dx + wy * dy) / length, (wy * dx - wx * dy) / length
        def world(v):
            return (p[0] + c * (v[0] - a[0]) - s * (v[1] - a[1]),
                    p[1] + s * (v[0] - a[0]) + c * (v[1] - a[1]))
        assert max(math.dist(world(v), raw[edge[0]]) for v, edge in
                   zip(graph['outline'], graph['source_edges'])) < 1e-5
        footprint = analyze(raw); partition = decompose(footprint)
        diagnostic = partition.inspect()
        points = [footprint.frame.world_xy(v) for v in diagnostic['vertices']]
        for panel, title in zip(panels[line], ('Minimum Cells (analysis only)',
                'Historical separate roofs (222037b)', 'Declared continuous polygon model',
                'Installed operator: fixed RoofGraph')):
            panel.set_title(title, fontsize=11); panel.set_aspect('equal'); panel.axis('off')
            panel.add_patch(Polygon(raw, facecolor='#f1f4f7', edgecolor='#555'))
        for cell in diagnostic['cells']:
            polygon = [points[v] for v in cell['boundary']]
            panels[line, 0].add_patch(Polygon(polygon, facecolor=plt.cm.Set3(cell['id'] % 12),
                                                edgecolor='#555', linewidth=1))
            middle = [sum(v[k] for v in polygon) / len(polygon) for k in (0, 1)]
            panels[line, 0].text(*middle, 'C' + str(cell['id']), ha='center', fontsize=10)
        before = old[row['name']]
        for edge in before['features']:
            first, second = (before['vertices'][v] for v in edge['vertices'])
            panels[line, 1].plot((first[0], second[0]), (first[1], second[1]),
                                 color=colors[edge['kind']], linewidth=2)
        for end in data['architecture']['ends']:
            index = end['edge']; first, second = (world(graph['outline'][v])
                                      for v in (index, (index + 1) % len(graph['outline'])))
            color = '#7039b8' if end['shape'] == 'gable' else '#167958'
            panels[line, 2].plot((first[0], second[0]), (first[1], second[1]), color=color,
                                 linewidth=3)
            panels[line, 2].text((first[0] + second[0]) / 2, (first[1] + second[1]) / 2,
                                 str(index), fontsize=9)
        causes = []
        vertices = [world(v) for v in data['solved_vertices']]
        for index, edge in enumerate(graph['edges']):
            first, second = (vertices[v] for v in edge['vertices'])
            panels[line, 3].plot((first[0], second[0]), (first[1], second[1]),
                                 color=colors[edge['kind']], linewidth=2)
            if edge['kind'] in ('ridge', 'hip', 'valley'):
                feature = next(f for f in data['features'] if f['vertices'] == edge['vertices'])
                causes.append('E' + str(index) + ' ' + edge['kind'] + ' <- region 0; eaves ' +
                              str(feature['source_eaves']))
                panels[line, 3].text((first[0] + second[0]) / 2, (first[1] + second[1]) / 2,
                                     'E' + str(index), fontsize=8)
        panels[line, 0].text(0, -.08, row['name'], transform=panels[line, 0].transAxes, fontsize=8)
        panels[line, 1].text(0, -.08, 'Historical core render; not the user live revision',
                             transform=panels[line, 1].transAxes, fontsize=8)
        panels[line, 2].text(0, -.08, 'Purple: gable end; green: eave. Cells are not roof supports.',
                             transform=panels[line, 2].transAxes, fontsize=8)
        panels[line, 3].text(0, -.08, '\n'.join(causes), transform=panels[line, 3].transAxes,
                             fontsize=7, va='top')
        for panel in panels[line]:
            panel.autoscale_view(); panel.margins(.15)
    figure.suptitle('Architecture and feature causes: red ridge / blue valley / orange hip\n'
                    'Screenshot approximations; declared polygon and exterior ends precede global incidence',
                    fontsize=13)
    figure.subplots_adjust(top=.93, bottom=.08, hspace=.9, wspace=.3)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output)
    if args.output.suffix.lower() == '.svg':
        svg = args.output.read_text(encoding='utf-8')
        args.output.write_text('\n'.join(line.rstrip() for line in svg.splitlines()) + '\n',
                               encoding='utf-8', newline='\n')
    figure.savefig(args.output.with_suffix('.png'), dpi=100)
    print('Recorded cases:', len(rows))


if __name__ == '__main__':
    main()
