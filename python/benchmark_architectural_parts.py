# SPDX-License-Identifier: GPL-3.0-or-later
"""Uncached architectural stages; no roof topology, geometry solve or mesh."""

import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "addon"))
from roof_generator.core.footprint import analyze
from roof_generator.core.partition_candidates import candidates
from roof_generator.core.architecture import analyze_parts, build_parts
from roof_generator.core.architecture_selection import (
    evaluate,
    retained_indices,
    Policy,
    Recommendation,
)
from inspect_architectural_parts import fixture
from benchmark_graph_first import stats  # existing reporting contract, unchanged


def measure(record, policy):
    row = {}
    start = t = time.perf_counter()
    fp = analyze(record["footprint"])
    now = time.perf_counter()
    row["footprint_analysis"] = (now - t) * 1000
    t = now
    search = candidates(fp)
    now = time.perf_counter()
    row["partition_candidates"] = (now - t) * 1000
    t = now
    analyses = tuple(analyze_parts(d) for d in search.candidates)
    now = time.perf_counter()
    row["architectural_interpretation"] = (now - t) * 1000
    t = now
    evaluations = tuple(
        evaluate(d, a, policy) for d, a in zip(search.candidates, analyses)
    )
    indices = retained_indices(search, evaluations)
    now = time.perf_counter()
    row["candidate_evaluation"] = (now - t) * 1000
    t = now
    retained = tuple(
        (i, build_parts(search.candidates[i], analyses[i])) for i in indices
    )
    now = time.perf_counter()
    row["selected_part_graph_construction"] = (now - t) * 1000
    row["footprint_to_part_interpretation"] = (now - start) * 1000
    return row, Recommendation(search, policy, evaluations, retained)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--samples", type=int, default=25)
    p.add_argument("--warmup", type=int, default=3)
    p.add_argument(
        "--output",
        type=Path,
        default=ROOT / "python/out/interpretation/performance.json",
    )
    args = p.parse_args()
    if args.samples < 5 or args.warmup < 1:
        p.error("use >=5 samples and >=1 warmup")
    data = {
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            ).strip()
        ),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "samples": args.samples,
        "warmup": args.warmup,
        "profiled": False,
        "cache": "none",
        "policy": {"fragment_metres": 3, "metres_per_unit": 1},
        "cases": {},
    }
    for name in (
        "orthogonal_U",
        "cross",
        "residential_multi_reflex",
        "grid_14",
        "grid_20",
        "grid_40",
    ):
        record = fixture(name)
        rows = []
        for i in range(args.warmup + args.samples):
            row, out = measure(record, Policy())
            if i >= args.warmup:
                rows.append(row)
        data["cases"][name] = {
            "corners": len(out.search.candidates[0].footprint.vertices),
            "minimum_cells": len(out.search.candidates[0].cells),
            "search": out.search.inspect(),
            "status": out.status,
            "retained": [i for i, _ in out.retained],
            "parts": [len(g.parts) for _, g in out.retained],
            "stages": {k: stats([r[k] for r in rows]) for k in rows[0]},
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                name: {
                    "candidates": r["search"]["candidate_count"],
                    "retained": len(r["retained"]),
                    "median_ms": r["stages"]["footprint_to_part_interpretation"][
                        "median_ms"
                    ],
                }
                for name, r in data["cases"].items()
            }
        )
    )


if __name__ == "__main__":
    main()
