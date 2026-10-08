# SPDX-License-Identifier: GPL-3.0-or-later
"""Staged, separate-corpus audit. Blender is unmeasured outside Blender."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
sys.path.insert(0, str(ROOT))
from roof_generator.core.footprint import analyze
from roof_generator.core.partition_candidates import candidates
from roof_generator.core.architecture_selection import recommend, Policy
from roof_generator.core.topology_candidates import build_candidates, partition_id
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.core.solve import solve
from roof_generator.core.optimization import optimize

STAGES = (
    "footprint",
    "partition",
    "architecture",
    "RoofGraph",
    "GeometryProblem",
    "solve",
    "mesh",
    "Blender",
)


def classify(pool):
    """Retain evidence, not a guess that a vocabulary name specifies a rewrite.

    A/B can be observed only where another retained assignment produces a valid
    graph. Otherwise these remain joint B/C/F questions pending research; they
    are NOT automatically classified C. Downstream solve is censored.
    """
    good = {partition_id(c.architecture.decomposition) for c in pool.valid}
    result = []
    for r in pool.rejected:
        for issue in r.issues:
            key = issue.stage + "." + issue.code
            if pool.valid:
                category = "B" if r.partition in good else "A"
                evidence = (
                    "another axis/interpretation succeeds"
                    if category == "B"
                    else "another retained minimum partition succeeds"
                )
            elif issue.stage == "relation":
                category = "unresolved_B_C_F"
                evidence = "relation identified; no proved rewrite or alternative successful interpretation"
            else:
                category = "C" if issue.stage == "junction" else "unresolved_C_D_F"
                evidence = "published restricted junction applicability failed; downstream embedding not evaluated"
            result.append(
                {
                    "code": key,
                    "category": category,
                    "owner": (
                        "architecture" if issue.stage == "relation" else "topology"
                    ),
                    "cells": issue.cells,
                    "partition": r.partition,
                    "axes": r.axes,
                    "evidence": evidence,
                }
            )
    return result


def inspect(record):
    row = {
        "name": record["name"],
        "success": {k: False for k in STAGES},
        "failure_owner": None,
        "reason": None,
        "issues": [],
        "timings_ms": {},
        "Blender_measured": False,
    }
    owner = "footprint"
    t = time.perf_counter()

    def completed(stage):
        nonlocal t
        now = time.perf_counter()
        row["success"][stage] = True
        row["timings_ms"][stage] = (now - t) * 1000
        t = now

    try:
        fp = analyze(record["footprint"])
        completed("footprint")
        owner = "partition"
        search = candidates(fp)
        if not search.complete or not search.candidates:
            raise UnsupportedRoofError(search.reason or "no complete partition")
        completed("partition")
        row["partition_count"] = len(search.candidates)
        owner = "architecture"
        interpretation = recommend(search, Policy(), defer_ranking=True)
        if not interpretation.retained:
            raise UnsupportedRoofError("no architectural interpretation")
        completed("architecture")
        row["interpretation_count"] = len(interpretation.retained)
        owner = "topology"
        pool = build_candidates(interpretation)
        row["issues"] = classify(pool)
        row["valid_graph_count"] = len(pool.valid)
        if not pool.complete or not pool.valid:
            row["incomplete_search"] = not pool.complete
            raise UnsupportedRoofError(pool.reason or "no valid topology")
        completed("RoofGraph")
        selected = pool.select(0)
        row["selected_id"] = selected.id
        completed("GeometryProblem")
        owner = "solve"
        # Separate optimizer convergence from mesh validation. Exact primitive
        # solve includes validation; compound coordinates can be checked alone.
        if len(selected.architecture.members) > 1:
            embedding = optimize(selected.geometry)
            completed("solve")
            owner = "mesh"
            from roof_generator.core.mesh import RoofMesh

            mesh = RoofMesh(selected.graph, embedding.vertices)
        else:
            mesh = solve(selected.graph, selected.geometry)
            completed("solve")
        owner = "mesh"
        # Constructor validates exactly the solved graph; no triangulation/repair.
        type(mesh)(mesh.graph, mesh.vertices)
        completed("mesh")
    except (UnsupportedRoofError, ValueError) as exc:
        row["failure_owner"] = owner
        row["reason"] = str(exc)
    row["timings_ms"]["total"] = (
        sum(row["timings_ms"].values()) + (time.perf_counter() - t) * 1000
    )
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--details", type=Path, required=True)
    p.add_argument("--limit", type=int)
    a = p.parse_args()
    payload = gzip.decompress(a.corpus.read_bytes())
    data = json.loads(payload)
    out = {
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)
        ),
        "corpus_sha256": hashlib.sha256(payload).hexdigest(),
        "generator_version": data["version"],
        "seed": data["seed"],
        "Blender": "not measured; see Blender smoke report",
        "corpora": {},
    }
    a.details.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(a.details, "wt") as f:
        for category, records in data["corpora"].items():
            if a.limit:
                records = records[: a.limit]
            counts, failures, reasons, issues, sole = (Counter() for _ in range(5))
            elapsed = 0.0
            for i, record in enumerate(records):
                row = inspect(record)
                row["corpus"] = category
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
                counts.update(k for k, v in row["success"].items() if v)
                if row["failure_owner"]:
                    failures[row["failure_owner"]] += 1
                if row["reason"]:
                    reasons[row["reason"]] += 1
                codes = {r["code"] for r in row["issues"]}
                issues.update(codes)
                if not row["success"]["RoofGraph"]:
                    per_candidate = {}
                    for issue in row["issues"]:
                        per_candidate.setdefault(
                            (issue["partition"], tuple(issue["axes"])), set()
                        ).add(issue["code"])
                    sole.update(
                        {next(iter(s)) for s in per_candidate.values() if len(s) == 1}
                    )
                elapsed += row["timings_ms"]["total"]
                if (i + 1) % 100 == 0:
                    print(category, i + 1, len(records), flush=True)
            out["corpora"][category] = {
                "inputs": len(records),
                "success": {k: counts[k] for k in STAGES},
                "failure_owner": dict(failures),
                "issue_building_incidence_nonexclusive": dict(issues),
                "conditional_sole_assignment_blocker": dict(sole),
                "failure_reasons": dict(reasons),
                "total_ms": elapsed,
            }
            print(category, dict(counts), flush=True)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
