# SPDX-License-Identifier: GPL-3.0-or-later
"""Uncached, unprofiled partition stages and a batch of distinct footprints."""

import argparse
from collections import Counter
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from python.graph_first.footprint import analyze
from python.graph_first.cells import decompose, from_subdivision
from python.graph_first.rectangle_partition import (
    good_diagonals,
    intersection_graph,
    maximum_matching,
    independent_set,
    Selection,
    complete_cuts,
    subdivide,
)
from python.tests.grid_footprints import (
    generated,
)  # Input creation only, outside timing.


def stats(values):
    ordered = sorted(values)
    index = 0.95 * (len(values) - 1)
    lo = int(index)
    hi = min(lo + 1, len(values) - 1)
    return {
        "median_ms": statistics.median(values),
        "p95_ms": ordered[lo] + (index - lo) * (ordered[hi] - ordered[lo]),
        "samples_ms": values,
    }


def measure(points):
    row = {}
    start = time.perf_counter()
    t = start
    fp = analyze(points)
    now = time.perf_counter()
    row["analysis"] = (now - t) * 1000
    t = now
    diagonals = good_diagonals(fp)
    now = time.perf_counter()
    row["diagonals"] = (now - t) * 1000
    t = now
    left, right, conflicts = intersection_graph(fp, diagonals)
    now = time.perf_counter()
    row["intersection_graph"] = (now - t) * 1000
    t = now
    matching = maximum_matching(left, right, conflicts)
    now = time.perf_counter()
    row["matching"] = (now - t) * 1000
    t = now
    selected = independent_set(left, right, conflicts, matching)
    selection = Selection(diagonals, conflicts, matching, selected)
    now = time.perf_counter()
    row["independent_set"] = (now - t) * 1000
    t = now
    completions = complete_cuts(fp, selection)
    now = time.perf_counter()
    row["completion"] = (now - t) * 1000
    t = now
    subdivision = subdivide(fp, selection, completions)
    now = time.perf_counter()
    row["subdivision"] = (now - t) * 1000
    t = now
    result = from_subdivision(fp, subdivision)
    now = time.perf_counter()
    row["cell_records"] = (now - t) * 1000
    row["partition_after_analysis"] = (now - start) * 1000 - row["analysis"]
    row["total"] = (now - start) * 1000
    return row, result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--samples", type=int, default=101)
    p.add_argument("--warmup", type=int, default=5)
    p.add_argument("--buildings", type=int, default=1000)
    p.add_argument(
        "--output", type=Path, default=ROOT / "python/out/partition/performance.json"
    )
    args = p.parse_args()
    if args.samples < 5 or args.warmup < 1 or args.buildings < 1:
        p.error("positive buildings, >=5 samples and >=1 warmup required")
    fixtures = json.loads(
        (ROOT / "python/tests/fixtures/rectangle_partition.json").read_text()
    )
    by_name = {c["name"]: c for c in fixtures}
    selected_names = (
        "orthogonal_L",
        "orthogonal_T",
        "orthogonal_U",
        "residential_multi_reflex",
        "cross",
        "staircase",
        "comb",
        "comb_40",
    )
    cases = {name: by_name[name]["footprint"] for name in selected_names}
    pool = list(generated(max(args.buildings, 100), seed=92821))
    batch = pool[: args.buildings]
    for vertices in (14, 20, 40):
        cases[f"grid_{vertices}"] = next(
            points for points in batch if len(points) == vertices
        )
    report = {
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            ).strip()
        ),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "profiled": False,
        "cache": "none",
        "samples": args.samples,
        "warmup": args.warmup,
        "input_generation_timed": False,
        "cases": {},
    }
    for name, points in cases.items():
        rows = []
        for index in range(args.samples + args.warmup):
            row, d = measure(points)
            if index >= args.warmup:
                rows.append(row)
        timings = {stage: stats([r[stage] for r in rows]) for stage in rows[0]}
        cert = d.certificate
        s = cert.selection
        report["cases"][name] = {
            "footprint": points,
            "corners": len(d.footprint.vertices),
            "reflex": len(cert.reflex),
            "good_diagonals": len(s.diagonals),
            "conflicts": len(s.conflicts),
            "matching_size": len(s.matching),
            "selected": s.selected,
            "cells": len(d.cells),
            "timings": timings,
        }
        print(
            f'{name}: {len(d.footprint.vertices)} corners, {len(d.cells)} cells, {timings["total"]["median_ms"]:.3f}ms median',
            flush=True,
        )
    # Distinct geometry inputs, no memoization and no repeating one cached roof.
    start = time.perf_counter()
    cells = 0
    per_building = []
    for points in batch:
        t = time.perf_counter()
        d = decompose(analyze(points))
        per_building.append((time.perf_counter() - t) * 1000)
        cells += len(d.cells)
    elapsed = time.perf_counter() - start
    report["batch"] = {
        "buildings": len(batch),
        "distinct_footprints": len(set(batch)),
        "seed": 92821,
        "corner_histogram": dict(sorted(Counter(map(len, batch)).items())),
        "cells": cells,
        "seconds": elapsed,
        "per_building": stats(per_building),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"{len(batch)} distinct buildings: {elapsed:.3f}s", flush=True)


if __name__ == "__main__":
    main()
