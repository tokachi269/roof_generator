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
from roof_generator.core.topology_candidates import partition_id
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.core.solve import embed
from roof_generator.core.mesh import RoofMesh
from roof_generator.core.roof_candidates import roof_candidates,RoofCandidates
from roof_generator.core.generation import GenerationSettings
from roof_generator.core.architecture_models import ArchitecturalPartGraph
from roof_generator.core.cells import decompose
from roof_generator.core.polygon_generation import candidates as polygon_candidates, PolygonCandidates
from roof_generator.core.wavefront import WavefrontBudget

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
    if isinstance(pool,PolygonCandidates):
        return [{'code':'polygon.'+r.stage,'category':'D' if r.stage=='embedding' else 'unresolved_C_D_F',
                 'owner':'geometry' if r.stage=='embedding' else 'topology',
                 'gable_edges':r.gable_edges,'evidence':r.reason,
                 'authority_evidence':'resolved continuous polygon model; no Cell junction inference'} for r in pool.rejected]
    good = {partition_id(c.architecture.decomposition) for c in pool.valid
            if isinstance(c.architecture,ArchitecturalPartGraph)}
    regional_success=any(not isinstance(c.architecture,ArchitecturalPartGraph) for c in pool.valid)
    result = []
    for r in pool.rejected:
        for issue in r.issues:
            key = issue.stage + "." + issue.code
            if pool.valid and regional_success and r.partition not in good:
                category='C_candidate_region_alternative'
                evidence='another region/model family has an embedded roof; abandoned Cell contacts are not inferred junctions'
            elif pool.valid:
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
                        "architecture" if issue.stage in {"relation","ends","model","architecture"} else
                        "geometry" if issue.stage == "embedding" else "topology"
                    ),
                    "cells": issue.cells,
                    "partition": r.partition,
                    "axes": r.axes,
                    "evidence": evidence,
                    "architectural_scope": (
                        "internal" if issue.code.startswith("internal_") else
                        "inter_part" if issue.code.startswith("inter_part_") else "operation_applicability"
                    ),
                    "authority_classification": (
                        "C_alternative_partition" if pool.valid and r.partition not in good else
                        "unresolved_A_B_E" if issue.code.startswith("internal_") else
                        "unresolved_B_D_E" if issue.stage == "relation" else "B_restricted_operation"
                    ),
                    "authority_evidence": (
                        "Part grouping alone does not specify how this analytic relation becomes a roof; no junction-free continuation is proved"
                        if issue.code.startswith("internal_") else
                        "declared inter-Part contact; footprint-only grammar/ambiguity remains unresolved"
                        if issue.stage == "relation" else
                        "declared architecture exists but the proved operation applicability is not satisfied"
                    ),
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
        if fp.orthogonal:
            decompose(fp)
            completed('partition')
            row['partition_count']=1
            row['partition_scope']='classical minimum guide; polygon models own topology'
            owner='topology'
            pool=polygon_candidates(fp,GenerationSettings())
            row['success']['architecture']=bool(pool.interpretation.models)
            row['interpretation_count']=len(pool.interpretation.models)
            row['architecturally_retained_candidate_count']=len(pool.interpretation.models)
            row['architectural_preferred_assignment_count']=len(pool.interpretation.models)
            row['architectural_assignment_count']=len(pool.interpretation.models)
            row['issues']=classify(pool)
            row['valid_graph_count']=len(pool.valid)
            row['constructible_topology_candidate_count']=len(pool.constructible)
            row['region_proposal_count']=len(pool.interpretation.guides)
            row['ambiguity']=len(pool.valid)>1
            row['incomplete_search']=not pool.complete
            row['candidate_validation_scope']='all preferred polygon end models embedded before selection'
            if pool.constructible:
                completed('RoofGraph');completed('GeometryProblem')
            if not pool.complete or not pool.valid:
                if pool.constructible and pool.complete:owner='solve'
                raise UnsupportedRoofError(pool.reason or 'no valid polygon roof')
            selected=pool.select(0);row['selected_id']=selected.id
            owner='solve';vertices=pool.mesh(selected).vertices
            row['solve_timing_scope']='embedding occurs during candidate validation; solve stage reads cached proof'
            completed('solve')
            owner='mesh';RoofMesh(selected.graph,vertices);completed('mesh')
            row['timings_ms']['total']=sum(row['timings_ms'].values())+(time.perf_counter()-t)*1000
            return row
        search = candidates(fp)
        row["incomplete_search"] = not search.complete
        if search.complete and search.candidates:
            completed("partition")
        else:
            row['timings_ms']['partition']=(time.perf_counter()-t)*1000
            t=time.perf_counter()
        row["partition_count"] = len(search.candidates)
        owner = "architecture"
        interpretation = recommend(search, Policy(), defer_ranking=True)
        if interpretation.retained:completed("architecture")
        row["interpretation_count"] = len(interpretation.retained)
        row["architecturally_retained_candidate_count"] = len(interpretation.retained)
        owner = "topology"
        pool = roof_candidates(fp,interpretation,GenerationSettings())
        if not interpretation.retained and isinstance(pool,RoofCandidates) and pool.regions.architectural:
            row['success']['architecture']=True
        row["issues"] = classify(pool)
        row["valid_graph_count"] = len(pool.valid)
        row["constructible_topology_candidate_count"] = len(pool.constructible)
        ranking=pool.minimum.inspect_ranking() if isinstance(pool,RoofCandidates) else pool.inspect_ranking()
        row["architectural_preferred_assignment_count"] = len(ranking["architectural_preferred_assignments"])
        row["architectural_assignment_count"] = len(pool.architectural)
        if isinstance(pool,RoofCandidates):
            row['region_proposal_count']=len(pool.regions.proposals)
            row['region_architectural_assignment_count']=len(pool.regions.architectural)
            row['region_embedded_candidate_count']=len(pool.regions.valid)
            row['candidate_validation_scope']='all orthogonal gable families embedded before selection'
        row["ambiguity"] = len(pool.valid) > 1
        if pool.valid:
            completed("RoofGraph")
            completed("GeometryProblem")
        if not pool.complete or not pool.valid:
            row["incomplete_search"] = not pool.complete
            if not search.complete:owner='partition'
            raise UnsupportedRoofError(pool.reason or "no valid topology")
        selected = pool.select(0)
        row["selected_id"] = selected.id
        row["timings_ms"]["seed"] = (time.perf_counter() - t) * 1000
        t = time.perf_counter()
        owner = "solve"
        vertices = (pool.mesh(selected).vertices if isinstance(pool,RoofCandidates)
                    else embed(selected.graph, selected.geometry))
        if isinstance(pool,RoofCandidates):
            row['solve_timing_scope']='embedding occurs inside RoofGraph candidate validation; solve stage reads cached proof'
        completed("solve")
        owner = "mesh"
        # Constructor validates exactly the solved graph; no triangulation/repair.
        RoofMesh(selected.graph, vertices)
        completed("mesh")
    except (UnsupportedRoofError, ValueError) as exc:
        if isinstance(exc, WavefrontBudget):
            row['incomplete_search'] = True
            owner = 'search'
        row["failure_owner"] = owner
        row["reason"] = str(exc)
        row["failure"] = {
            "owner": owner,
            "code": (
                "incomplete_search"
                if row.get("incomplete_search")
                else (
                    "unsupported_decomposition"
                    if owner == "partition" and row["success"]["footprint"]
                    else (
                        "invalid_embedding"
                        if owner in {"solve", "mesh"}
                        else "no_valid_candidate"
                    )
                )
            ),
            "categories": (
                ["D"]
                if owner in {"solve", "mesh"}
                else (
                    ["F"]
                    if owner in {"footprint", "partition"}
                    else sorted({i["category"] for i in row["issues"]})
                )
            ),
            "research_scope": "current algorithm/input contract; not a claim of geometric impossibility",
        }
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
    p.add_argument('--category',action='append')
    p.add_argument('--seconds',type=float,default=15)
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
            if a.category and category not in a.category:continue
            if a.limit:
                records = records[: a.limit]
            counts, failures, reasons, issues, sole = (Counter() for _ in range(5))
            elapsed = 0.0
            candidate_counts = Counter()
            for i, record in enumerate(records):
                try:
                    run=subprocess.run([sys.executable,'-c',
                        'import json,sys; from python.audit_coverage import inspect; print(json.dumps(inspect(json.load(sys.stdin))))'],
                        cwd=ROOT,input=json.dumps(record),capture_output=True,text=True,timeout=a.seconds)
                    if run.returncode:raise RuntimeError(run.stderr[-2000:])
                    row=json.loads(run.stdout)
                except subprocess.TimeoutExpired:
                    row={'name':record['name'],'success':{k:False for k in STAGES},
                         'failure_owner':'search','reason':'per-input wall budget exhausted',
                         'issues':[],'incomplete_search':True,'censored':True,
                         'failure':{'owner':'search','code':'incomplete_search'},
                         'timings_ms':{'total':a.seconds*1000},
                         'timing_scope':'wall budget includes process and imports; no feasibility claim'}
                row["corpus"] = category
                candidate_counts.update({k: row.get(k, 0) for k in (
                    "architecturally_retained_candidate_count", "constructible_topology_candidate_count",
                    "architectural_preferred_assignment_count", "architectural_assignment_count",
                )})
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
                f.flush()
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
                        if 'partition' not in issue:
                            continue  # Polygon models are not minimum assignments.
                        per_candidate.setdefault(
                            (issue["partition"], tuple(issue["axes"])), set()
                        ).add(issue["code"])
                    sole.update(
                        {next(iter(s)) for s in per_candidate.values() if len(s) == 1}
                    )
                elapsed += row["timings_ms"]["total"]
                if (i + 1) % 25 == 0:
                    print(category, i + 1, len(records), flush=True)
            out["corpora"][category] = {
                "inputs": len(records),
                "success": {k: counts[k] for k in STAGES},
                "failure_owner": dict(failures),
                "issue_building_incidence_nonexclusive": dict(issues),
                "conditional_sole_assignment_blocker": dict(sole),
                "failure_reasons": dict(reasons),
                "total_ms": elapsed,
                "candidate_counts": dict(candidate_counts),
            }
            print(category, dict(counts), flush=True)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
