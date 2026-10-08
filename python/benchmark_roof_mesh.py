# SPDX-License-Identifier: GPL-3.0-or-later
"""Unprofiled selected topology/solve/mesh budget; optional source-root pairing."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--code-root", type=Path, default=Path(__file__).resolve().parents[1])
p.add_argument("--samples", type=int, default=7)
p.add_argument("--buildings", type=int, default=1000)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
ROOT = a.code_root.resolve()
sys.path[:0] = [str(ROOT / "addon"), str(Path(__file__).resolve().parent)]
# Load the requested package before developer tools adjust their import paths.
from roof_generator.core.generation import prepare_generation
from roof_generator.core.solve import solve
from roof_generator.core.optimization import optimize
from roof_generator.core.mesh import RoofMesh
from benchmark_generation import measure, fingerprint, NAMES
from inspect_architectural_parts import fixture
from measurements import stats


def measured(record):
    row, interpretation, pool, choices = measure(record)
    row["solve"] = row["mesh"] = 0.0
    supported = False
    embedding = None
    if pool.complete and pool.valid:
        c = pool.select(0)
        start = time.perf_counter()
        if len(c.architecture.members) > 1:
            embedding = optimize(c.geometry)
            row["solve"] = (time.perf_counter() - start) * 1000
            start = time.perf_counter()
            mesh = RoofMesh(c.graph, embedding.vertices)
            row["mesh"] = (time.perf_counter() - start) * 1000
        else:
            mesh = solve(c.graph, c.geometry)
            row["solve"] = (time.perf_counter() - start) * 1000
        supported = True
    row["core_total"] = row["total"] + row["solve"] + row["mesh"]
    return row, fingerprint(interpretation, pool, choices), supported, embedding


out = {
    "source_sha": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip(),
    "python": platform.python_version(),
    "profiled": False,
    "persistent_cache": False,
    "seed_selection_samples": [0, 1, 7, 42],
    "cases": {},
}
records = {n: fixture(n) for n in NAMES}
for name, record in records.items():
    rows = []
    for i in range(a.samples + 2):
        row, proof, supported, embedding = measured(record)
        if i >= 2:
            rows.append(row)
    out["cases"][name] = {
        "fingerprint": proof,
        "mesh_success": supported,
        "vertices": len(record["footprint"]),
        "stages": {k: stats([r[k] for r in rows]) for k in rows[0]},
    }
    if embedding:
        out["cases"][name]["embedding"] = {
            "iterations": embedding.iterations,
            "energy": embedding.energy,
            "planarity_error": embedding.planarity_error,
            "direction_error": embedding.direction_error,
            "slope_error": embedding.slope_error,
        }
count = 0
start = time.perf_counter()
for i in range(a.buildings):
    row, proof, supported, _ = measured(records[NAMES[i % len(NAMES)]])
    count += supported
out["repeated_six_fixture_batch"] = {
    "inputs": a.buildings,
    "mesh_success": count,
    "total_ms": (time.perf_counter() - start) * 1000,
    "scope": "performance batch, not coverage of unknown buildings",
}
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(out, indent=2) + "\n")
print(
    {
        n: round(r["stages"]["core_total"]["median_ms"], 2)
        for n, r in out["cases"].items()
    },
    flush=True,
)
