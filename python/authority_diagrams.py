# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare recorded Cells, Parts, relations and roof feature causes in one SVG."""

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape


def svg(before, after, *, solved=False):
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1100" viewBox="0 0 1440 1100">',
           '<rect width="1440" height="1100" fill="white"/>',
           '<g font-family="sans-serif" font-size="13" fill="#17212b">']
    palette = ("#daeafa", "#f9e1d2", "#dcefd8", "#eddcf3", "#faedbc", "#d4efea")
    for row, data in enumerate((before, after)):
        d, architecture = data["partition"], data["architecture"]
        nodes = d["vertices"]
        low = [min(p[k] for p in nodes) for k in (0, 1)]
        span = max(max(p[k] for p in nodes) - low[k] for k in (0, 1))
        scale = 345 / span
        offset = row * 540
        def point(p, panel):
            return (35 + panel * 480 + (p[0] - low[0]) * scale, offset + 405 - (p[1] - low[1]) * scale)
        def chain(indices, pts, panel):
            return " ".join(f"{point(pts[i],panel)[0]:.2f},{point(pts[i],panel)[1]:.2f}" for i in indices)
        label = "BEFORE" if row == 0 else "AFTER"
        for panel, title in enumerate(("Minimum Cells / artificial cuts", "ArchitecturalParts / declared relations", "Final roof features / recorded causes")):
            out.append(f'<text x="{35+panel*480}" y="{offset+30}">{label}: {title}</text>')
        owners = {c: p["id"] for p in architecture["parts"] for c in p["cells"]}
        centers = {}
        for cell in d["cells"]:
            c = cell["id"]
            centers[c] = tuple(sum(nodes[v][k] for v in cell["corners"]) / 4 for k in (0, 1))
            for panel in (0, 1):
                color = palette[(c if panel == 0 else owners[c]) % len(palette)]
                out.append(f'<polygon points="{chain(cell["boundary"],nodes,panel)}" fill="{color}" stroke="#99a5b1" stroke-width="1"/>')
                x, y = point(centers[c], panel)
                out.append(f'<text x="{x:.2f}" y="{y:.2f}">C{c}' + (f'/P{owners[c]}' if panel else '') + '</text>')
        for adjacent in d["adjacency"]:
            out.append(f'<polyline points="{chain(adjacent["interval"],nodes,0)}" fill="none" stroke="#283645" stroke-width="2" stroke-dasharray="6,4"/>')
        for index, relation in enumerate(architecture["relations"]):
            a, b = (point(centers[c], 1) for c in relation["cells"])
            kinds = "/".join(sorted({o["kind"] for o in relation["options"]}))
            decisions = (data.get("resolved_ends") or {}).get("joints", ())
            choice = next((j["kind"] for j in decisions if j["cells"] == relation["cells"]), None)
            if choice:
                kinds += " -> " + choice
            scope = "internal" if len({owners[c] for c in relation["cells"]}) == 1 else "inter-part"
            out.append(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="#00867e" stroke-width="2"/>')
            out.append(f'<text x="515" y="{offset+435+index*16}">R{index}: C{relation["cells"]} {escape(kinds)} ({scope})</text>')
        if data["graph"]:
            graph = data["graph"]
            pts = data["solved_vertices"] if solved else [v["seed"] for v in graph["vertices"]]
            features = {tuple(f["vertices"]): f for f in data["features"]}
            colors = {"ridge": "#cd2941", "valley": "#1469c9", "hip": "#da871c", "eave": "#637283", "gable_end": "#637283"}
            legend = []
            for i, edge in enumerate(graph["edges"]):
                cause = features.get(tuple(edge["vertices"]))
                detail = f'E{i} {edge["kind"]}'
                if cause:
                    relation = next((j for j, r in enumerate(architecture["relations"]) if r["cells"] == list(cause["relation"])), None) if cause["relation"] else None
                    detail += f' <- {cause["operation"]} ' + (f'R{relation}' if relation is not None else f'C{cause["members"]}') + f' / P{cause["parts"]}'
                elif len(edge["faces"]) == 2:
                    detail += ' (cause unrecorded)'
                out.append(f'<polyline points="{chain(edge["vertices"],pts,2)}" fill="none" stroke="{colors[edge["kind"]]}" stroke-width="3"><title>{escape(detail)}</title></polyline>')
                if len(edge["faces"]) == 2:
                    center = tuple(sum(pts[v][k] for v in edge["vertices"]) / 2 for k in (0, 1))
                    x, y = point(center, 2)
                    out.append(f'<text x="{x+3:.2f}" y="{y-3:.2f}">E{i}</text>')
                    legend.append(detail)
            # Full provenance is in JSON and tooltips; the compact legend keeps
            # dense networks readable without changing any actual feature.
            for j, detail in enumerate(legend[:6]):
                out.append(f'<text x="995" y="{offset+420+j*16}">{escape(detail)}</text>')
        else:
            out.append(f'<text x="995" y="{offset+160}">UNSUPPORTED: no final RoofGraph</text>')
        geometry = "solved embedding" if solved else "topology initializer"
        out.append(f'<text x="35" y="{offset+520}">{escape(data["architecture_scope"])}; roof XY is the {geometry}. Red ridge / blue valley / orange hip.</text>')
    out.append('</g></svg>')
    return "\n".join(out) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for b, a in zip(before, after):
        assert b["input"] == a["input"]
        (args.output_dir / (a["input"]["name"] + ".svg")).write_text(svg(b, a), encoding="utf-8")


if __name__ == "__main__":
    main()
