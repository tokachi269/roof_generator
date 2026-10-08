# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure published junctions with the existing graph-first stage harness."""

import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from python.benchmark_graph_first import measure, stats
from python.graph_first.graph import UnsupportedGraphError
from python.tests.composition_footprints import buildings


def cases():
    partition = json.loads(
        (ROOT / "python/tests/fixtures/rectangle_partition.json").read_text()
    )
    result = [
        r
        for r in partition
        if r["name"]
        in {
            "orthogonal_L",
            "orthogonal_T",
            "orthogonal_U",
            "cross",
            "residential_multi_reflex",
        }
    ]
    for r in json.loads(
        (ROOT / "python/tests/fixtures/roof_composition.json").read_text()
    ):
        if r["name"] in {"middle_equal", "middle_offset", "multiple_disjoint_middle"}:
            result.append(
                {
                    "name": r["name"],
                    "footprint": [r["points"][v][:2] for v in r["outline"]],
                }
            )
    for n in (14, 20, 40):
        result.append(
            json.loads((ROOT / f"python/docs/partition/grid_{n}.json").read_text())[
                "input"
            ]
        )
    generated = list(buildings())
    for n in (20, 40):
        r = next(c for c in generated if len(c["footprint"]) == n)
        result.append(dict(r, name=f"grid_branches_{n}", generator_seed=4107))
    return [dict(r, roof_type="gable", pitch=0.5) for r in result]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=101)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--buildings", type=int, default=1000)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "python/out/composition/performance.json"
    )
    args = parser.parse_args()
    if args.samples < 5 or args.warmup < 1 or args.buildings < 1:
        parser.error("use at least 5 samples, 1 warmup and 1 building")
    report = {
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            )
        ),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "samples": args.samples,
        "warmup": args.warmup,
        "profiled": False,
        "cache": "none",
        "input_generation_timed": False,
        "stage_harness": "unchanged benchmark_graph_first.measure",
        "scope": "supported graph composition and geometry-problem export; no nonlinear solve/mesh",
        "cases": {},
    }
    for case in cases():
        try:
            row, c = measure(case)
        except UnsupportedGraphError as exc:
            report["cases"][case["name"]] = {
                "status": "unsupported",
                "reason": str(exc),
            }
            continue
        for _ in range(args.warmup):
            measure(case)
        rows = [measure(case)[0] for _ in range(args.samples)]
        g = c.graph
        report["cases"][case["name"]] = {
            "status": "supported",
            "input": case,
            "vertices_edges_faces": [len(g.vertices), len(g.edges), len(g.faces)],
            "features": g.inspect()["features"],
            "stages": {key: stats([r[key] for r in rows]) for key in row},
        }
    pool = [dict(r, roof_type="gable", pitch=0.5) for r in buildings(args.buildings)]
    start = time.perf_counter()
    rows = [measure(r)[0] for r in pool]
    elapsed = time.perf_counter() - start
    report["batch"] = {
        "seed": 4107,
        "buildings": len(pool),
        "distinct_footprints": len({r["footprint"] for r in pool}),
        "domain": "longitudinal main rectangle plus separated narrower middle branches; excludes unresolved architecture",
        "seconds_including_geometry_problem_and_timing": elapsed,
        "stages": {key: stats([r[key] for r in rows]) for key in rows[0]},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        f"{args.output}: {len(pool)} distinct supported buildings, {elapsed:.3f}s; no nonlinear solve"
    )


if __name__ == "__main__":
    main()
