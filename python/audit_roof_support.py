# SPDX-License-Identifier: GPL-3.0-or-later
"""Audit every rejected assignment, separately from supported building counts.

Relations are checked together. Downstream junctions are not examined after a
relation failure: a sole blocker is a conditional upper bound, never a promise
that implementing it will produce a valid roof. No meshes or solver are run.
"""

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
sys.path.insert(0, str(ROOT))
from roof_generator.core.topology_candidates import partition_id
from benchmark_generation import NAMES, measure, fingerprint
from inspect_architectural_parts import fixture
from python.tests.grid_footprints import generated


def inspect_record(record):
    timings, recommendation, pool, choices = measure(record)
    architectures = {
        partition_id(a.decomposition): a for _, a in recommendation.retained
    }
    rejected = []
    continuation = Counter()
    for r in pool.rejected:
        issues = [asdict(i) for i in r.issues]
        rejected.append(
            {
                "partition": r.partition,
                "axes": r.axes,
                "reason": r.reason,
                "issues": issues,
            }
        )
        architecture = architectures[r.partition]
        for issue in r.issues:
            if issue.stage != "relation" or issue.code != "continuation":
                continue
            # Independent dimension check: can both full ends be rectangularly
            # merged? Such a pair would contradict the minimum-cell certificate.
            a, b = (architecture.members[c] for c in issue.cells)
            axis = r.axes[a.cell]
            transverse = 1 - axis
            aligned = all(
                abs(a.bounds[k] - b.bounds[k]) < 1e-8
                for k in (transverse, transverse + 2)
            )
            continuation[
                "aligned_equal_width" if aligned else "offset_or_width_step"
            ] += 1
    return {
        "name": record["name"],
        "vertices": len(record["footprint"]),
        "partition_candidates": len(recommendation.search.candidates),
        "retained_interpretations": len(recommendation.retained),
        "valid": len(pool.valid),
        "rejected": rejected,
        "complete": pool.complete,
        "status": (
            "incomplete"
            if not pool.complete
            else "supported" if pool.valid else "unsupported"
        ),
        "fingerprint": fingerprint(recommendation, pool, choices),
        "continuation_geometry": dict(continuation),
        "timings_ms": timings,
    }


def summarize(rows):
    status, buildings, unsupported, candidate, occurrence = (
        Counter() for _ in range(5)
    )
    sole, continuation, messages = Counter(), Counter(), Counter()
    total_ms = 0.0
    for row, weight in rows:
        total_ms += row["timings_ms"]["total"] * weight
        status[row["status"]] += weight
        seen = set()
        for rejected in row["rejected"]:
            keys = [i["stage"] + "." + i["code"] for i in rejected["issues"]]
            occurrence.update({k: keys.count(k) * weight for k in set(keys)})
            candidate.update({k: weight for k in set(keys)})
            messages[rejected["reason"]] += weight
            seen.update(keys)
        buildings.update({k: weight for k in seen})
        if row["status"] == "unsupported":
            unsupported.update({k: weight for k in seen})
            only = {
                next(iter(keys))
                for r in row["rejected"]
                if len(keys := {i["stage"] + "." + i["code"] for i in r["issues"]}) == 1
            }
            sole.update({k: weight for k in only})
        continuation.update(
            {k: v * weight for k, v in row["continuation_geometry"].items()}
        )
    ordered = lambda c: dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))
    return {
        "building_status": ordered(status),
        "building_incidence_nonexclusive": ordered(buildings),
        "unsupported_building_incidence_nonexclusive": ordered(unsupported),
        "rejected_assignment_incidence_nonexclusive": ordered(candidate),
        "issue_occurrences": ordered(occurrence),
        "conditional_sole_known_blocker_buildings": ordered(sole),
        "continuation_geometry_occurrences": ordered(continuation),
        "raw_rejection_messages": ordered(messages),
        "total_ms": total_ms,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--grid-count", type=int, default=1000)
    p.add_argument("--seed", type=int, default=92821)
    p.add_argument("--grid-scale", type=float, default=3.0)
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--details", type=Path, required=True)
    args = p.parse_args()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    )
    if args.corpus.exists():
        records = json.loads(args.corpus.read_text())
    else:
        records = [
            {
                "name": f"generated_{i:04}",
                "footprint": [
                    [args.grid_scale * x, args.grid_scale * y] for x, y in raw
                ],
            }
            for i, raw in enumerate(generated(args.grid_count, args.seed))
        ]
        args.corpus.parent.mkdir(parents=True, exist_ok=True)
        args.corpus.write_text(json.dumps(records, separators=(",", ":")) + "\n")
    fixtures = [inspect_record(dict(fixture(n), name=n)) for n in NAMES]
    vertex_histogram = Counter()
    args.details.parent.mkdir(parents=True, exist_ok=True)
    with args.details.open("w") as f:

        def inspected():
            for i, record in enumerate(records):
                row = inspect_record(record)
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
                vertex_histogram[row["vertices"]] += 1
                if (i + 1) % 100 == 0:
                    print(f"audited {i + 1}/{len(records)}", flush=True)
                yield row, 1

        # Fold statistics immediately; never retain all rejected assignments
        # from the whole corpus in memory. Full details remain a streamed file.
        unique_summary = summarize(inspected())
    weights = Counter(NAMES[i % len(NAMES)] for i in range(1000))
    data = {
        "source_sha": revision,
        "source_dirty": dirty,
        "corpus_sha256": hashlib.sha256(args.corpus.read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "profiled": False,
        "scope": "2D RoofGraph + GeometryProblem; not solved meshes",
        "corpus_generator_seed": args.seed,
        "grid_scale_metres": args.grid_scale,
        "censoring": "Junction/geometry failures after a blocked relation are unobserved. Sole known blockers are upper bounds.",
        "fixtures": [
            {k: v for k, v in row.items() if k != "rejected"} for row in fixtures
        ],
        "repeated_six_fixtures_1000": summarize(
            [(r, weights[r["name"]]) for r in fixtures]
        ),
        "unique_generated_grid": unique_summary,
        "unknown_vertex_histogram": dict(sorted(vertex_histogram.items())),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data["unique_generated_grid"]["building_status"]), flush=True)


if __name__ == "__main__":
    main()
