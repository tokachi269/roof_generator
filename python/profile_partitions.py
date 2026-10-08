# SPDX-License-Identifier: GPL-3.0-or-later
"""Partition stage timing without changing enumeration or instrumenting core."""

import argparse
import cProfile
import json
from pathlib import Path
import pstats
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "addon"), str(ROOT / "python")]
from roof_generator.core import partition_candidates as pc, partition, cells
from roof_generator.core.footprint import analyze
from inspect_architectural_parts import fixture


def profile():
    fp = analyze(fixture("grid_40")["footprint"])
    timers = {}
    counts = {}

    def wrap(module, name, label):
        original = getattr(module, name)

        def measured(*args, **kwargs):
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                timers[label] = (
                    timers.get(label, 0) + (time.perf_counter() - start) * 1000
                )
                counts[label] = counts.get(label, 0) + 1

        return patch.object(module, name, measured)

    original_sets = pc.maximum_sets

    def enumeration(*args, **kwargs):
        iterator = original_sets(*args, **kwargs)
        while True:
            start = time.perf_counter()
            try:
                value = next(iterator)
            except StopIteration:
                timers["MIS_enumeration"] = (
                    timers.get("MIS_enumeration", 0)
                    + (time.perf_counter() - start) * 1000
                )
                return
            timers["MIS_enumeration"] = (
                timers.get("MIS_enumeration", 0) + (time.perf_counter() - start) * 1000
            )
            counts["MIS_enumeration"] = counts.get("MIS_enumeration", 0) + 1
            yield value

    # Inclusive times are labelled: parent stages contain their child costs.
    with wrap(pc, "complete_cuts", "completion"), wrap(
        pc, "symmetries", "symmetry_detection"
    ), wrap(pc, "_cut_signature", "cut_signature"), wrap(
        pc, "subdivide", "subdivision_inclusive"
    ), wrap(
        pc, "from_subdivision", "cell_materialization_inclusive"
    ), wrap(
        partition, "_node_segments", "noding"
    ), wrap(
        partition, "_partition_faces", "face_cycles"
    ), wrap(
        partition, "_validate_partition", "subdivision_validation"
    ), wrap(
        cells, "_boundary_span", "provenance"
    ), wrap(
        cells, "_validate_provenance", "provenance_validation"
    ):
        start = time.perf_counter()
        search = pc.candidates(fp)
        total = (time.perf_counter() - start) * 1000
    return {
        "input": "grid_40",
        "vertices": len(fp.vertices),
        "candidates": len(search.candidates),
        "work": search.work,
        "instrumented_total_ms": total,
        "inclusive_ms": timers,
        "calls": counts,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(profile(), indent=2) + "\n")
    profiler = cProfile.Profile()
    profiler.runcall(pc.candidates, analyze(fixture("grid_40")["footprint"]))
    with a.output.with_suffix(".txt").open("w") as f:
        pstats.Stats(profiler, stream=f).sort_stats("cumtime").print_stats(35)
