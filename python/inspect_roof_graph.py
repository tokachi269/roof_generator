# SPDX-License-Identifier: GPL-3.0-or-later
"""Export cells, primitive/composed 2D graphs and the pre-solver geometry problem."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "addon"))
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose
from roof_generator.core.topology import compose
from roof_generator.core.solve import problem


def svg(decomposition, composition):
    """Debug drawing only: does not alter graph positions or incidence."""
    points = decomposition.vertices
    g = composition.graph
    lo = [min(p[k] for p in points) for k in (0, 1)]
    hi = [max(p[k] for p in points) for k in (0, 1)]
    scale = 370 / max(hi[k] - lo[k] for k in (0, 1))

    def point(p, panel):
        return (40 + panel * 480 + (p[0] - lo[0]) * scale, 455 - (p[1] - lo[1]) * scale)

    def chain(ids, nodes, panel):
        return " ".join(
            f"{point(nodes[i],panel)[0]:.3f},{point(nodes[i],panel)[1]:.3f}"
            for i in ids
        )

    text = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="525" viewBox="0 0 960 525">',
        '<rect width="960" height="525" fill="white"/>',
        '<g font-family="sans-serif" font-size="14" fill="#18212b">',
        '<text x="40" y="30">Cells / artificial boundary</text>',
        '<text x="520" y="30">2D RoofGraph before geometry solve</text>',
    ]
    palette = ("#e0eefb", "#f9e5d7")
    for cell in decomposition.cells:
        text.append(
            f'<polygon points="{chain(cell.boundary,points,0)}" fill="{palette[cell.id%2]}" stroke="#586779" stroke-width="2"/>'
        )
        centre = tuple(sum(points[i][k] for i in cell.corners) / 4 for k in (0, 1))
        x, y = point(centre, 0)
        text.append(f'<text x="{x:.3f}" y="{y:.3f}">cell {cell.id}</text>')
    for adjacency in decomposition.adjacency:
        text.append(
            f'<polyline points="{chain(adjacency.interval,points,0)}" fill="none" stroke="#222" stroke-width="3" stroke-dasharray="7,5"/>'
        )
    colors = {
        "ridge": "#d63143",
        "valley": "#1767cf",
        "hip": "#dc8818",
        "eave": "#586779",
        "gable_end": "#586779",
    }
    nodes = tuple(v.seed for v in g.vertices)
    for edge in g.edges:
        text.append(
            f'<polyline points="{chain(edge.vertices,nodes,1)}" fill="none" stroke="{colors[edge.kind]}" stroke-width="3"><title>{escape(edge.kind)}: {edge.vertices}, faces {edge.faces}</title></polyline>'
        )
    for i, vertex in enumerate(g.vertices):
        x, y = point(vertex.seed, 1)
        text.append(
            f'<circle cx="{x:.3f}" cy="{y:.3f}" r="4" fill="#18212b"/><text x="{x+7:.3f}" y="{y-7:.3f}">{i}</text>'
        )
    text.append(
        '<text x="40" y="505">Red: ridge; blue: valley; orange: hip. XY is an initializer, not solved roof geometry.</text></g></svg>'
    )
    return "\n".join(text) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--fixture", help="Debug input from the acceptance fixture file"
    )
    source.add_argument(
        "--input", type=Path, help="JSON with footprint, roof_type and optional pitch"
    )
    parser.add_argument("--roof-type", choices=("gable", "hip", "shed", "flat"))
    parser.add_argument(
        "--output", type=Path, default=ROOT / "python/out/graph-first/inspection.json"
    )
    args = parser.parse_args()
    if args.fixture:
        records = json.loads(
            (ROOT / "python/tests/fixtures/roof_acceptance.json").read_text()
        )
        record = next((c for c in records if c["name"] == args.fixture), None)
        if record is None:
            parser.error("unknown debug fixture")
    else:
        record = json.loads(args.input.read_text())
    fp = analyze(record["footprint"])
    cells = decompose(fp)
    composition = compose(cells, args.roof_type or record.get("roof_type", "gable"))
    geometry = problem(composition.graph, record.get("pitch", 0.5))
    document = {
        "schema": 2,
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "input": record,
        "frame": asdict(fp.frame),
        "analysis": {
            "vertices": fp.vertices,
            "source_edges": fp.source_edges,
            "directions": fp.directions,
            "reflex": fp.reflex,
            "parallel": fp.parallel,
        },
        "decomposition": cells.inspect(),
        "composition": composition.inspect(),
        "geometry_problem": asdict(geometry),
        "solver_status": "pre-solver problem only",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n")
    args.output.with_suffix(".svg").write_text(svg(cells, composition))
    print(
        f"{args.output}: {len(cells.cells)} cells, {len(composition.graph.faces)} roof faces; no nonlinear solve"
    )


if __name__ == "__main__":
    main()
