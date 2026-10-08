# SPDX-License-Identifier: GPL-3.0-or-later
"""Developer-only nested stage probe and cProfile; never performance targets."""

import argparse
from contextlib import contextmanager
import cProfile
import functools
import json
from pathlib import Path
import pstats
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from roof_generator.core import partition, partition_candidates, cells
from roof_generator.core.footprint import analyze
from benchmark_generation import measure
from inspect_architectural_parts import fixture


@contextmanager
def partition_probe():
    """Restore every instrumented function; report inclusive and exclusive time."""
    rows = {}
    stack = []
    originals = []

    def wrap(owner, name, label):
        original = getattr(owner, name)

        @functools.wraps(original)
        def observed(*args, **kwargs):
            item = [time.perf_counter(), 0.0]
            stack.append(item)
            try:
                return original(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - item[0]
                stack.pop()
                row = rows.setdefault(
                    label, {"calls": 0, "inclusive_ms": 0.0, "exclusive_ms": 0.0}
                )
                row["calls"] += 1
                row["inclusive_ms"] += elapsed * 1000
                row["exclusive_ms"] += (elapsed - item[1]) * 1000
                if stack:
                    stack[-1][1] += elapsed

        originals.append((owner, name, original))
        setattr(owner, name, observed)

    for owner, name, label in (
        (partition_candidates, "candidates", "partition_total"),
        (partition_candidates, "good_diagonals", "good_diagonals"),
        (partition_candidates, "select_diagonals", "matching_certificate"),
        (partition_candidates, "symmetries", "symmetry_detection"),
        (partition_candidates, "complete_cuts", "completion_generation"),
        (partition_candidates, "_cut_signature", "cut_signature_dedup"),
        (partition_candidates.Symmetry, "apply", "symmetry_point_expansion"),
        (partition_candidates, "subdivide", "subdivision"),
        (partition, "_node_segments", "noding"),
        (partition, "_partition_faces", "face_cycles"),
        (partition, "_validate_partition", "subdivision_validation"),
        (partition_candidates, "from_subdivision", "cell_materialization"),
        (cells, "_boundary_span", "provenance"),
        (cells, "_validate_provenance", "provenance_validation"),
    ):
        wrap(owner, name, label)
    original = partition_candidates.maximum_sets

    def observed_sets(*args, **kwargs):
        iterator = original(*args, **kwargs)
        while True:
            t = time.perf_counter()
            try:
                value = next(iterator)
            except StopIteration:
                return
            elapsed = (time.perf_counter() - t) * 1000
            row = rows.setdefault(
                "MIS_enumeration",
                {"calls": 0, "inclusive_ms": 0.0, "exclusive_ms": 0.0},
            )
            row["calls"] += 1
            row["inclusive_ms"] += elapsed
            row["exclusive_ms"] += elapsed
            if stack:
                stack[-1][1] += elapsed / 1000
            yield value

    originals.append((partition_candidates, "maximum_sets", original))
    partition_candidates.maximum_sets = observed_sets
    try:
        yield rows
    finally:
        for owner, name, original in reversed(originals):
            setattr(owner, name, original)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixture", default="grid_40")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    record = fixture(args.fixture)
    fp = analyze(record["footprint"])
    with partition_probe() as stages:
        search = partition_candidates.candidates(fp)
    profile = cProfile.Profile()
    profile.runcall(measure, record)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    profile.dump_stats(str(args.output.with_suffix(".pstats")))
    with args.output.with_suffix(".txt").open("w") as output:
        pstats.Stats(profile, stream=output).sort_stats("cumulative").print_stats(45)
    args.output.write_text(
        json.dumps(
            {
                "fixture": args.fixture,
                "instrumented": True,
                "nested_times": True,
                "candidates": len(search.candidates),
                "work": search.work,
                "stages": stages,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(stages))


if __name__ == "__main__":
    main()
