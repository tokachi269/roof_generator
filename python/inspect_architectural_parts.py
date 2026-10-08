# SPDX-License-Identifier: GPL-3.0-or-later
"""Inspect minimum alternatives and architectural units; no roof lines or mesh."""

import argparse
from dataclasses import asdict
from html import escape
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "addon"))
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose
from roof_generator.core.partition_candidates import candidates
from roof_generator.core.architecture_selection import recommend, Policy


def fixture(name):
    rows = json.loads(
        (ROOT / "python/tests/fixtures/rectangle_partition.json").read_text(
            encoding="utf-8"
        )
    )
    record = next((r for r in rows if r["name"] == name), None)
    if record is None:
        p = ROOT / "python/docs/partition" / f"{name}.json"
        if not p.is_file():
            raise ValueError("unknown inspection fixture")
        record = json.loads(p.read_text(encoding="utf-8"))["input"]
    return record


def inspect(record, policy=Policy(), **budgets):
    points = record["footprint"] if isinstance(record, dict) else record
    fp = analyze(points)
    primary = decompose(fp)
    search = candidates(fp, **budgets)
    out = recommend(search, policy)
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
        "primary": primary.inspect(),
        "candidate_partitions": [d.inspect() for d in search.candidates],
        "interpretation": out.inspect(),
        "summary": {
            "corners": len(fp.vertices),
            "minimum_cells": len(primary.cells),
            "candidates": len(search.candidates),
            "retained": len(out.retained),
            "status": out.status,
            "part_counts": [len(g.parts) for _, g in out.retained],
            "consumed_counts": [
                sum(len(p.consumed) for p in g.parts) for _, g in out.retained
            ],
        },
    }
    return data


def svg(data):
    """Read inspection records only. Analytic relation arrows are never ridges."""
    interpretation = data["interpretation"]
    pool = data["candidate_partitions"]
    retained = {r["candidate"]: r["graph"] for r in interpretation["retained"]}
    n = len(pool)
    columns = 4
    tile_w = 350
    tile_h = 340
    gallery_rows = math.ceil(n / columns)
    detail_rows = math.ceil(len(retained) / columns)
    width = columns * tile_w
    detail_start = 620 + gallery_rows * tile_h
    height = detail_start + 80 + detail_rows * tile_h
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6" fill="#176a85"/></marker></defs>',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        '<g font-family="sans-serif" fill="#18212b">',
        f'<text x="25" y="30" font-size="22">Architectural part interpretation: {escape(str(data["input"].get("name","input") if isinstance(data["input"],dict) else "input"))}</text>',
        f'<text x="25" y="56">{n} minimum candidates; {len(retained)} retained; {escape(interpretation["status"])}</text>',
        '<text x="25" y="82">Intrinsic XY. No roof primitives, ridge / valley / hip, heights or solver.</text>',
        '<text x="25" y="108">Gray dashed: retained analytic cut. Green dotted: consumed inside compound part.</text>',
        '<text x="25" y="134">Teal arrows: member attachment toward receiver (conditional when marked ?), not roof edges.</text>',
    ]
    palette = ("#dbe9fa", "#f8ddc5", "#dfedda", "#f2dced", "#e6e2fd", "#f7ecc4")

    def panel(d, x, y, title, graph=None, w=tile_w, h=tile_h):
        nodes = d["vertices"]
        lo = [min(p[k] for p in nodes) for k in (0, 1)]
        hi = [max(p[k] for p in nodes) for k in (0, 1)]
        scale = min((w - 50) / (hi[0] - lo[0]), (h - 85) / (hi[1] - lo[1]))

        def xy(p):
            return x + 25 + (p[0] - lo[0]) * scale, y + h - 40 - (p[1] - lo[1]) * scale

        def chain(ids):
            return " ".join(f"{xy(nodes[i])[0]:.2f},{xy(nodes[i])[1]:.2f}" for i in ids)

        out.append(
            f'<rect x="{x+3}" y="{y+3}" width="{w-6}" height="{h-6}" fill="none" stroke="#b7c6d1"/>'
        )
        out.append(f'<text x="{x+15}" y="{y+23}" font-size="13">{escape(title)}</text>')
        owners = (
            {c: p["id"] for p in graph["parts"] for c in p["cells"]}
            if graph
            else {c["id"]: c["id"] for c in d["cells"]}
        )
        centers = {}
        for cell in d["cells"]:
            color = palette[owners[cell["id"]] % len(palette)]
            out.append(
                f'<polygon points="{chain(cell["boundary"])}" fill="{color}" stroke="none"/>'
            )
            ps = [nodes[i] for i in cell["corners"]]
            center = tuple(sum(p[k] for p in ps) / 4 for k in (0, 1))
            centers[cell["id"]] = xy(center)
            cx, cy = xy(center)
            label = (
                f'c{cell["id"]}'
                if not graph
                else f'p{owners[cell["id"]]}:c{cell["id"]}'
            )
            out.append(
                f'<text x="{cx:.2f}" y="{cy:.2f}" font-size="11" text-anchor="middle">{label}</text>'
            )
        consumed = (
            {tuple(e) for p in graph["parts"] for e in p["consumed"]}
            if graph
            else set()
        )
        for a in d["adjacency"]:
            yes = tuple(a["interval"]) in consumed
            color = "#319267" if yes else "#707b88"
            dash = "2,4" if yes else "6,4"
            out.append(
                f'<polyline points="{chain(a["interval"])}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="{dash}"/>'
            )
        if graph:
            for p in graph["parts"]:
                for ring in p["boundaries"]:
                    artificial = {tuple(a["interval"]) for a in d["adjacency"]}
                    for a, b in zip(ring, ring[1:] + ring[:1]):
                        if tuple(sorted((a, b))) not in artificial:
                            out.append(
                                f'<polyline points="{chain((a,b))}" fill="none" stroke="#31445a" stroke-width="2"/>'
                            )
            for relation in graph["relations"]:
                options = relation["options"]
                seen = set()
                for option in options:
                    receiver, branch = option["receiver"], option["branch"]
                    if receiver is None or (receiver, branch) in seen:
                        continue
                    seen.add((receiver, branch))
                    bx, by = centers[branch]
                    hx, hy = centers[receiver]
                    out.append(
                        f'<path d="M{bx:.2f},{by:.2f} L{hx:.2f},{hy:.2f}" fill="none" stroke="#176a85" stroke-width="1.2" stroke-dasharray="3,4" marker-end="url(#arrow)"><title>{escape(option["kind"])}; main={option["main"]}; {"conditional" if len(options)>1 else "declared relation"}</title></path>'
                    )
                    if len(options) > 1:
                        out.append(
                            f'<text x="{(bx+hx)/2:.2f}" y="{(by+hy)/2:.2f}" font-size="13">?</text>'
                        )
            codes = (
                ",".join(sorted({i["code"] for i in graph["issues"]}))
                or "relations interpreted; topology pending"
            )
            out.append(
                f'<text x="{x+12}" y="{y+h-10}" font-size="10">{escape(codes)}</text>'
            )
        else:
            ring = tuple(range(data["summary"]["corners"]))
            out.append(
                f'<polygon points="{chain(ring)}" fill="none" stroke="#31445a" stroke-width="2"/>'
            )

    panel(
        data["primary"], 0, 160, "Established primary minimum partition", w=550, h=380
    )
    # World input is retained in JSON; primary is the same footprint in its frame.
    out.append(
        '<text x="600" y="205">All candidate thumbnails are minimum partitions.</text>'
    )
    out.append(
        '<text x="600" y="235">Retained candidates are not independent roof objects.</text>'
    )
    out.append(
        '<text x="600" y="265">Compound parts retain member geometry and local relations.</text>'
    )
    out.append(
        '<text x="600" y="295">An ambiguous recommendation has no selected main direction.</text>'
    )
    out.append(
        '<text x="25" y="595" font-size="19">Minimum candidate gallery; retained means eligible under published score bounds</text>'
    )
    for i, d in enumerate(pool):
        e = interpretation["evaluations"][i]
        flag = "RETAINED" if i in retained else "lower recommendation bound"
        title = f'#{i}: score {e["score"]}; {flag}'
        panel(d, (i % columns) * tile_w, 620 + (i // columns) * tile_h, title)
    out.append(
        f'<text x="25" y="{detail_start+45}" font-size="19">All retained ArchitecturalPart graphs; part colors and consumed cuts</text>'
    )
    for j, (i, g) in enumerate(retained.items()):
        panel(
            pool[i],
            (j % columns) * tile_w,
            detail_start + 80 + (j // columns) * tile_h,
            f'#{i}: {len(g["parts"])} compound/single units; {sum(len(p["consumed"]) for p in g["parts"])} cuts consumed',
            g,
        )
    out.append("</g></svg>")
    return "\n".join(out) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--fixture")
    source.add_argument("--input", type=Path)
    p.add_argument(
        "--output",
        type=Path,
        default=ROOT / "python/out/interpretation/inspection.json",
    )
    p.add_argument("--fragment-metres", type=float, default=3)
    p.add_argument("--metres-per-unit", type=float, default=1)
    p.add_argument("--max-candidates", type=int, default=4096)
    p.add_argument("--max-work", type=int, default=65536)
    args = p.parse_args()
    record = (
        fixture(args.fixture)
        if args.fixture
        else json.loads(args.input.read_text(encoding="utf-8"))
    )
    data = inspect(
        record,
        Policy(args.fragment_metres, args.metres_per_unit),
        max_candidates=args.max_candidates,
        max_work=args.max_work,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(data, allow_nan=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    args.output.with_suffix(".svg").write_text(svg(data), encoding="utf-8")
    print(json.dumps(data["summary"]))
    return 2 if data["summary"]["status"] == "incomplete" else 0


if __name__ == "__main__":
    raise SystemExit(main())
