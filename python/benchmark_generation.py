# SPDX-License-Identifier: GPL-3.0-or-later
"""Unprofiled canonical candidate stages, exact family fingerprints and batches."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from roof_generator.core.architecture_selection import Policy
from roof_generator.core.partition_candidates import signature
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.core.generation import GenerationSettings, generate_roof
import importlib.util
from roof_generator.core.topology_candidates import build_candidates
if importlib.util.find_spec('roof_generator.core.roof_candidates') is not None:
    from roof_generator.core.roof_candidates import roof_candidates
else:
    roof_candidates=None  # explicit older-code measurement capability
from roof_generator.core.footprint import analyze
from benchmark_architectural_parts import measure as measure_architecture
from inspect_architectural_parts import fixture
from measurements import stats

NAMES = (
    "orthogonal_U",
    "cross",
    "residential_multi_reflex",
    "grid_14",
    "grid_20",
    "grid_40",
)


def measure(record):
    start = time.perf_counter()
    row, recommendation = measure_architecture(record, Policy(), defer_ranking=True)
    t = time.perf_counter()
    pool = (roof_candidates(analyze(record['footprint']),recommendation,GenerationSettings())
            if roof_candidates is not None else build_candidates(recommendation))
    row["roof_topology_candidates"] = (time.perf_counter() - t) * 1000
    t = time.perf_counter()
    choices = []
    if pool.valid and pool.complete:
        choices = [pool.select(seed).id for seed in (0, 1, 7, 42)]
    row["seed_selection"] = (time.perf_counter() - t) * 1000
    row["total"] = (time.perf_counter() - start) * 1000
    return row, recommendation, pool, choices


def fingerprint(recommendation, pool, choices):
    proof = {
        "partitions": [signature(d) for d in recommendation.search.candidates],
        "architecture": recommendation.inspect(),
        "valid": [
            (c.id, c.axes, getattr(c,'score',None), c.graph.inspect(), c.geometry.__dict__)
            for c in pool.valid
        ],
        "rejected": [(r.partition, r.axes, r.reason) for r in pool.rejected],
        "complete": pool.complete,
        "choices": choices,
    }
    return hashlib.sha256(
        json.dumps(
            proof, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--samples", type=int, default=9)
    p.add_argument("--warmup", type=int, default=2)
    p.add_argument("--buildings", type=int, default=1000)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    records = {name: fixture(name) for name in NAMES}
    output = {
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
        "profiled": False,
        "persistent_cache": False,
        "seed_samples": [0, 1, 7, 42],
        "candidate_validation_scope": ("canonical families; orthogonal gable embedding precedes seed"
            if roof_candidates is not None else "older code: minimum topology/problem only"),
        "cases": {},
    }
    for name, record in records.items():
        rows = []
        cold = None
        for i in range(args.samples + args.warmup):
            row, recommendation, pool, choices = measure(record)
            if i == 0:
                cold = row
            if i >= args.warmup:
                rows.append(row)
        output["cases"][name] = {
            "vertices": len(recommendation.search.candidates[0].footprint.vertices),
            "candidates": len(recommendation.search.candidates),
            "work": recommendation.search.work,
            "retained_interpretations": len(recommendation.retained),
            "valid_topologies": len(pool.valid),
            "rejected_assignments": len(pool.rejected),
            "fingerprint": fingerprint(recommendation, pool, choices),
            "seed_choices": choices,
            "stages": {k: stats([row[k] for row in rows]) for k in rows[0]},
            "first_stages_ms": cold,
        }
    cache = getattr(getattr(sys.modules.get("roof_generator.core.member_layout"),
                            "minimum_layout", None), "cache_info", None)
    output["persistent_cache"] = cache is not None
    output["member_layout_cache_after_cases"] = cache()._asdict() if cache else None
    t = time.perf_counter()
    successful = 0
    for i in range(args.buildings):
        _, _, pool, _ = measure(records[NAMES[i % len(NAMES)]])
        successful += bool(pool.valid and pool.complete)
    output["mixed_buildings"] = {
        "count": args.buildings,
        "total_ms": (time.perf_counter() - t) * 1000,
        "geometry_problem_supported": successful,
        "unsupported": args.buildings - successful,
        "final_mesh_generated": roof_candidates is not None,
    }
    t = time.perf_counter()
    for i in range(args.buildings):
        generate_roof(((0, 0), (12, 0), (12, 6), (0, 6)), GenerationSettings(seed=i))
    output["rectangle_mesh_buildings"] = {
        "count": args.buildings,
        "total_ms": (time.perf_counter() - t) * 1000,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                n: {
                    "total_ms": d["stages"]["total"]["median_ms"],
                    "candidates": d["candidates"],
                    "valid": d["valid_topologies"],
                }
                for n, d in output["cases"].items()
            }
        )
    )


if __name__ == "__main__":
    main()
