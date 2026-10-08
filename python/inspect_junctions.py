# SPDX-License-Identifier: GPL-3.0-or-later
"""Inspect ports on one fixed minimum partition, without candidate selection.

For canonical support across all retained interpretations use inspect_roof.py.
A rejected fixed partition does not imply the footprint has no valid candidate.
"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import textwrap
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "addon"))
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose
from roof_generator.core.topology import compose, cell_primitives
from roof_generator.core.junctions import attachments
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.core.architecture import interpret, resolve
from roof_generator.core.solve import problem


def inspect(record):
    fp = analyze(record["footprint"])
    d = decompose(fp)
    roof_type = record.get("roof_type", "gable")
    primitives = cell_primitives(d, roof_type)
    architecture = interpret(d)
    resolved = resolve(architecture, tuple(m.axes[0] for m in architecture.members))
    try:
        candidates = attachments(resolved, primitives) if roof_type == "gable" else ()
    except UnsupportedRoofError:
        candidates = ()
    document = {
        "schema": 2,
        "scope": "one fixed partition and primitive orientation, not canonical candidate support",
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=ROOT,
                text=True,
            )
        ),
        "input": record,
        "frame": asdict(fp.frame),
        "decomposition": d.inspect(),
        "attachment_candidates": [a.inspect() for a in candidates],
        "primitive_candidates": [g.inspect() for g in primitives],
        "status": "unsupported",
        "composition": None,
        "geometry_problem": None,
        "solver_status": "no nonlinear solve",
    }
    try:
        c = compose(resolved, roof_type)
    except UnsupportedRoofError as exc:
        document["reason"] = str(exc)
    else:
        document["status"] = "supported"
        document["composition"] = c.inspect()
        document["geometry_problem"] = asdict(
            problem(c.graph, record.get("pitch", 0.5))
        )
    return document


def svg(document):
    """Draw only recorded decisions; candidate ridges are never final semantics."""
    d = document["decomposition"]
    nodes = d["vertices"]
    lo = [min(p[k] for p in nodes) for k in (0, 1)]
    size = max(max(p[k] for p in nodes) - lo[k] for k in (0, 1))
    scale = 325 / size

    def xy(p, panel):
        return (35 + panel * 440 + (p[0] - lo[0]) * scale, 395 - (p[1] - lo[1]) * scale)

    def path(points, panel):
        return " ".join(f"{x:.3f},{y:.3f}" for x, y in (xy(p, panel) for p in points))

    text = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1320" height="485" viewBox="0 0 1320 485">',
        '<rect width="1320" height="485" fill="white"/>',
        '<g font-family="sans-serif" font-size="13" fill="#18212b">',
        '<text x="35" y="25">Cells / cuts / adjacency</text>',
        '<text x="475" y="25">Primitive ridge candidates / ports</text>',
        '<text x="915" y="25">Final RoofGraph / junctions (before solve)</text>',
    ]
    palette = ("#e0eefb", "#f9e5d7", "#e2f0dd", "#eee2f6")
    centers = {}
    for cell in d["cells"]:
        points = [nodes[i] for i in cell["boundary"]]
        text.append(
            f'<polygon points="{path(points,0)}" fill="{palette[cell["id"]%4]}" stroke="#8a94a0" stroke-width="1"/>'
        )
        centers[cell["id"]] = tuple(
            sum(nodes[i][k] for i in cell["corners"]) / 4 for k in (0, 1)
        )
    for a in d["adjacency"]:
        text.append(
            f'<polyline points="{path([nodes[i] for i in a["interval"]],0)}" fill="none" stroke="#576474" stroke-width="2.5" stroke-dasharray="6,4"/>'
        )
        text.append(
            f'<polyline points="{path([centers[i] for i in a["cells"]],0)}" fill="none" stroke="#00918e" stroke-width="1.4"/>'
        )
    for i, p in centers.items():
        x, y = xy(p, 0)
        text.append(f'<text x="{x:.3f}" y="{y:.3f}">C{i}</text>')
    for primitive in document["primitive_candidates"]:
        points = [v["seed"] for v in primitive["vertices"]]
        text.append(
            f'<polygon points="{path(primitive["outline"],1)}" fill="none" stroke="#afb7bf" stroke-width="1"/>'
        )
        for e in primitive["edges"]:
            if e["kind"] == "ridge":
                text.append(
                    f'<polyline points="{path([points[i] for i in e["vertices"]],1)}" fill="none" stroke="#b07d89" stroke-width="2.5" stroke-dasharray="5,4"/>'
                )
        for v in primitive["vertices"]:
            if v["role"] == "ridge_end":
                x, y = xy(v["seed"], 1)
                text.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="3" fill="#b07d89"/>')
    if document["composition"]:
        g = document["composition"]["graph"]
        points = [v["seed"] for v in g["vertices"]]
        colors = {
            "ridge": "#d63143",
            "valley": "#1767cf",
            "hip": "#dc8818",
            "eave": "#586779",
            "gable_end": "#586779",
        }
        for e in g["edges"]:
            text.append(
                f'<polyline points="{path([points[i] for i in e["vertices"]],2)}" fill="none" stroke="{colors[e["kind"]]}" stroke-width="2.7"><title>{escape(e["kind"])}: {e["vertices"]}, faces {e["faces"]}</title></polyline>'
            )
        for v in g["vertices"]:
            if v["role"] == "junction":
                x, y = xy(v["seed"], 2)
                text.append(
                    f'<circle cx="{x:.3f}" cy="{y:.3f}" r="4.5" fill="#18212b"/><text x="{x+6:.3f}" y="{y-6:.3f}">J{v["id"]}</text>'
                )
    else:
        text.append(
            '<text x="915" y="70" fill="#b82234">UNSUPPORTED — no final graph</text>'
        )
        for i, line in enumerate(textwrap.wrap(document["reason"], 48)):
            text.append(f'<text x="915" y="{100+20*i}">{escape(line)}</text>')
    text.append(
        '<text x="35" y="447">Dashed gray: artificial cut; teal: cell adjacency. Dashed pink: candidates only.</text><text x="35" y="467">Final red: ridge; blue: valley; orange: hip; black: junction. XY is disposable initialization, not solved roof geometry.</text></g></svg>'
    )
    return "\n".join(text) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--input", type=Path, help="Ordered XY array or record containing footprint"
    )
    source.add_argument("--fixture", help="Debug case from rectangle_partition.json")
    parser.add_argument("--roof-type", choices=("gable", "hip", "shed", "flat"))
    parser.add_argument(
        "--output", type=Path, default=ROOT / "python/out/composition/inspection.json"
    )
    args = parser.parse_args()
    if args.fixture:
        cases = json.loads(
            (ROOT / "python/tests/fixtures/rectangle_partition.json").read_text(
                encoding="utf-8"
            )
        )
        record = next((r for r in cases if r["name"] == args.fixture), None)
        if record is None:
            parser.error("unknown debug fixture")
    else:
        record = json.loads(args.input.read_text(encoding="utf-8"))
        if isinstance(record, list):
            record = {"footprint": record}
    if args.roof_type:
        record["roof_type"] = args.roof_type
    document = inspect(record)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    args.output.with_suffix(".svg").write_text(svg(document), encoding="utf-8")
    print(f'{document["status"]}: {args.output}; no nonlinear solve')
    if document["status"] == "unsupported":
        print(document["reason"])
        raise SystemExit(2)


if __name__ == "__main__":
    main()
