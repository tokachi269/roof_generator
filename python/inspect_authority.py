# SPDX-License-Identifier: GPL-3.0-or-later
"""Paired, read-only architecture/feature inspection of frozen inputs."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--code-root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    sys.path.insert(0, str(args.code_root / "addon"))
    from roof_generator.core.footprint import analyze
    from roof_generator.core.partition_candidates import candidates
    from roof_generator.core.architecture_selection import recommend, Policy
    from roof_generator.core.topology_candidates import build_candidates
    from roof_generator.core.solve import solve
    from roof_generator.core.generation import GenerationSettings
    from roof_generator.core.roof_candidates import roof_candidates,RoofCandidates

    rows = []
    for record in json.loads(args.inputs.read_text(encoding="utf-8"))["inputs"]:
        fp=analyze(record['footprint'])
        recommendation = recommend(candidates(fp), Policy(), defer_ranking=True)
        pool = roof_candidates(fp,recommendation,GenerationSettings())
        candidate = pool.select(record.get("seed", 0)) if pool.complete and pool.valid else None
        architecture = candidate.architecture if candidate else recommendation.retained[0][1]
        row = {
            "input": record,
            "status": "supported" if candidate else "unsupported" if pool.complete else "incomplete",
            "selected_candidate": candidate.id if candidate else None,
            "resolved_ends": candidate.ends.inspect() if candidate and getattr(candidate, "ends", None) else None,
            "partition": recommendation.search.candidates[0].inspect(),
            "partition_scope": "first minimum source for provenance; supports are selected architecture",
            "architecture": architecture.inspect(),
            "architecture_scope": "selected" if candidate else "first diagnostic partition; no selected roof",
            "rejected": [asdict(r) for r in pool.rejected],
            "ranking": pool.inspect_ranking() if hasattr(pool, "inspect_ranking") else {"separate_sets": "unrecorded in baseline"},
            "graph": candidate.graph.inspect() if candidate else None,
            "connections": [asdict(c) for c in candidate.composition.connections] if candidate else [],
            "features": [asdict(f) for f in getattr(candidate.composition, "features", ())] if candidate else [],
            "feature_cause_scope": "recorded at construction" if candidate and hasattr(candidate.composition, "features") else "unrecorded in baseline or no roof",
            "independent_cell_roof_graphs": len(candidate.composition.primitives) if candidate else None,
        }
        if candidate:
            mesh = pool.mesh(candidate) if isinstance(pool,RoofCandidates) else solve(candidate.graph, candidate.geometry)
            row["solved_vertices"] = mesh.vertices
            row["solver_preserved_graph"] = mesh.graph is candidate.graph
        rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print([(r["input"]["name"], r["status"]) for r in rows])


if __name__ == "__main__":
    main()
