# SPDX-License-Identifier: GPL-3.0-or-later
"""Inspect a classical rectangular partition independently of roof generation."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "addon"))
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose


def svg(d):
    nodes = d.vertices
    lo = tuple(min(p[k] for p in nodes) for k in (0, 1))
    hi = tuple(max(p[k] for p in nodes) for k in (0, 1))
    scale = 600 / max(hi[k] - lo[k] for k in (0, 1))

    def xy(p):
        return 45 + (p[0] - lo[0]) * scale, 690 - (p[1] - lo[1]) * scale

    def chain(points):
        return " ".join(f"{xy(p)[0]:.3f},{xy(p)[1]:.3f}" for p in points)

    palette = ("#dbe9fa", "#f8ddc5", "#dfedda", "#f2dced", "#e6e2fd")
    text = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="760" viewBox="0 0 800 760">',
        '<rect width="800" height="760" fill="white"/>',
        '<g font-family="sans-serif" fill="#18212b" font-size="14">',
        f'<text x="35" y="28">Minimum rectangular partition: {len(d.cells)} cells</text>',
    ]
    for c in d.cells:
        text.append(
            f'<polygon points="{chain(nodes[i] for i in c.boundary)}" fill="{palette[c.id%len(palette)]}" stroke="#536273" stroke-width="1.5"/>'
        )
        center = tuple(sum(nodes[i][k] for i in c.corners) / 4 for k in (0, 1))
        x, y = xy(center)
        text.append(f'<text x="{x:.3f}" y="{y:.3f}">{c.id}</text>')
    selection = d.certificate.selection
    for i in selection.selected:
        points = [nodes[v] for v in selection.diagonals[i].endpoints]
        text.append(
            f'<polyline points="{chain(points)}" fill="none" stroke="#185dc7" stroke-width="3"><title>selected good diagonal {i}</title></polyline>'
        )
    for c in d.certificate.completions:
        text.append(
            f'<polyline points="{chain((c.start,c.end))}" fill="none" stroke="#26364a" stroke-width="2" stroke-dasharray="6,4"><title>completion from reflex {c.source}</title></polyline>'
        )
    text.append(
        '<text x="35" y="735">Blue: selected good diagonal. Dashed: reflex completion. No roof geometry.</text></g></svg>'
    )
    return "\n".join(text) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--fixture")
    group.add_argument(
        "--input", type=Path, help="JSON ordered XY points or {footprint: points}"
    )
    p.add_argument(
        "--output", type=Path, default=ROOT / "python/out/partition/inspection.json"
    )
    args = p.parse_args()
    if args.fixture:
        rows = json.loads(
            (ROOT / "python/tests/fixtures/rectangle_partition.json").read_text()
        )
        record = next((c for c in rows if c["name"] == args.fixture), None)
        if record is None:
            p.error("unknown partition fixture")
    else:
        record = json.loads(args.input.read_text())
    points = record["footprint"] if isinstance(record, dict) else record
    fp = analyze(points)
    d = decompose(fp)
    selection = d.certificate.selection
    data = {
        "schema": 1,
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            ).strip()
        ),
        "input": record,
        "frame": asdict(fp.frame),
        "analysis": {
            "vertices": fp.vertices,
            "source_edges": fp.source_edges,
            "reflex": fp.reflex,
        },
        "summary": {
            "corners": len(fp.vertices),
            "reflex": len(fp.reflex),
            "good_diagonals": len(selection.diagonals),
            "matching_size": len(selection.matching),
            "selected": selection.selected,
            "completions": len(d.certificate.completions),
            "cells": len(d.cells),
            "shared_intervals": len(d.adjacency),
        },
        "partition": d.inspect(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    args.output.with_suffix(".svg").write_text(svg(d))
    print(json.dumps(data["summary"]))


if __name__ == "__main__":
    main()
