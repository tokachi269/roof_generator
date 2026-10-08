# SPDX-License-Identifier: GPL-3.0-or-later
"""Uncached, unprofiled graph-first stages and unchanged reference measurements."""

import argparse
import json
import platform
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "addon"))
sys.path.insert(0, str(ROOT / "addon"))
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose
from roof_generator.core.topology import compose
from roof_generator.core.solve import problem, rectangle_vertices
from roof_generator.core.mesh import RoofMesh


def stats(samples):
    values = sorted(samples)
    index = 0.95 * (len(values) - 1)
    lo = int(index)
    hi = min(lo + 1, len(values) - 1)
    return {
        "median_ms": statistics.median(values),
        "p95_ms": values[lo] + (index - lo) * (values[hi] - values[lo]),
        "samples_ms": samples,
    }


def measure(case):
    row = {}
    start = time.perf_counter()
    t = start
    fp = analyze(case["footprint"])
    now = time.perf_counter()
    row["footprint_analysis"] = (now - t) * 1000
    t = now
    cells = decompose(fp)
    now = time.perf_counter()
    row["cell_decomposition"] = (now - t) * 1000
    t = now
    composition = compose(cells, case["roof_type"])
    now = time.perf_counter()
    row["roof_graph"] = (now - t) * 1000
    row["footprint_to_graph"] = (now - start) * 1000
    graph = composition.graph
    if len(cells.cells) == 1:
        t = time.perf_counter()
        vertices = rectangle_vertices(graph, case["pitch"])
        now = time.perf_counter()
        row["geometry_solve"] = (now - t) * 1000
        t = now
        mesh = RoofMesh(graph, vertices)
        now = time.perf_counter()
        row["mesh_conversion"] = (now - t) * 1000
        row["total_core"] = (now - start) * 1000
    else:
        t = time.perf_counter()
        problem(graph, case["pitch"])
        row["geometry_problem"] = (time.perf_counter() - t) * 1000
    return row, composition


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=101)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "python/out/graph-first/performance.json"
    )
    args = parser.parse_args()
    if args.samples < 5 or args.warmup < 1:
        parser.error("use >=5 samples and >=1 warmup")
    cases = json.loads(
        (ROOT / "python/tests/fixtures/roof_acceptance.json").read_text()
    )
    cases = [
        c
        for c in cases
        if c["name"]
        in (
            "rectangle_gable",
            "rectangle_hip",
            "rectangle_shed",
            "orthogonal_L",
            "rotated_L",
        )
    ]
    cases.insert(3, dict(cases[0], name="rectangle_flat", roof_type="flat"))
    # Imported only by the comparison harness, never by graph-first runtime.
    from python.benchmark_roof import clear_caches, stage_times
    from roof_generator.core.roof_building import generate_roof
    from roof_generator.core.roof_parts import RoofParameters

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
        "samples": args.samples,
        "warmup": args.warmup,
        "profiled": False,
        "new_cache": "none",
        "cases": {},
    }
    for case in cases:
        rows = []
        for index in range(args.warmup + args.samples):
            row, c = measure(case)
            if index >= args.warmup:
                rows.append(row)
        current = {stage: stats([r[stage] for r in rows]) for stage in rows[0]}
        current["SGA21_solve"] = None
        if len(c.primitives) == 2:
            current["geometry_solve"] = None
            current["mesh_conversion"] = None
            current["total_core"] = None
        record = {
            "graph_first": current,
            "reference": {},
            "graph": {
                "cells": len(c.primitives),
                "vertices": len(c.graph.vertices),
                "faces": len(c.graph.faces),
                "edges": len(c.graph.edges),
                "features": c.graph.inspect()["features"],
            },
        }
        for mode in ("cold", "warm"):
            clear_caches()
            legacy = []
            for index in range(args.warmup + args.samples):
                if mode == "cold":
                    clear_caches()
                with stage_times() as stages:
                    start = time.perf_counter()
                    generate_roof(
                        case["footprint"],
                        RoofParameters(case["roof_type"], pitch=case["pitch"]),
                    )
                    stages["total_core"] = (time.perf_counter() - start) * 1000
                stages["through_connection"] = sum(
                    stages[k] for k in ("normalize", "decompose", "connect")
                )
                if index >= args.warmup:
                    legacy.append(stages)
            record["reference"][mode] = {
                stage: stats([r[stage] for r in legacy]) for stage in legacy[0]
            }
        report["cases"][case["name"]] = record
        print(
            f"{case['name']}: graph {current['footprint_to_graph']['median_ms']:.3f}ms; reference through connection cold {record['reference']['cold']['through_connection']['median_ms']:.3f}ms",
            flush=True,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
