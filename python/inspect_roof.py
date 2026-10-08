# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only inspection of canonical partition, architecture and topology stages."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from roof_generator.core.footprint import analyze
from roof_generator.core.partition_candidates import candidates
from roof_generator.core.architecture_selection import recommend, Policy
from roof_generator.core.topology_candidates import build_candidates
from roof_generator.core.errors import UnsupportedRoofError
from inspect_architectural_parts import fixture
from roof_diagrams import svg


def inspect(record, seed=0, roof_type="gable"):
    fp = analyze(record["footprint"])
    search = candidates(fp)
    interpretation = recommend(
        search, None if roof_type == "flat" else Policy(), defer_ranking=True
    )
    pool = build_candidates(interpretation, roof_type)
    output = {
        "input": record,
        "seed": seed,
        "roof_type": roof_type,
        "partitions": search.inspect(),
        "architecture": interpretation.inspect(),
        "ranking": pool.inspect_ranking(),
        "valid_candidates": [
            {
                "id": c.id,
                "axes": c.axes,
                "score": c.score,
                "partition": c.architecture.decomposition.inspect(),
                "architectural_parts": c.architecture.inspect(),
                "resolved_ends": c.ends.inspect() if c.ends is not None else None,
                "graph": c.graph.inspect(),
                "composition": c.composition.inspect(),
                "geometry_problem": asdict(c.geometry),
            }
            for c in pool.valid
        ],
        "rejected": [asdict(r) for r in pool.rejected],
        "complete": pool.complete,
        "status": "unsupported",
        "selected": None,
        "selected_ends": None,
    }
    try:
        selected = pool.select(seed)
        output.update(status="geometry_problem", selected=selected.id,
                      selected_ends=selected.ends.inspect() if selected.ends is not None else None)
    except UnsupportedRoofError as exc:
        output["reason"] = str(exc)
    return output, pool


def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--fixture")
    source.add_argument("--input", type=Path)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--roof-type", choices=("gable", "hip", "shed", "flat"), default="gable"
    )
    p.add_argument(
        "--output", type=Path, default=ROOT / "python/out/roof/inspection.json"
    )
    args = p.parse_args()
    record = (
        fixture(args.fixture) if args.fixture else json.loads(args.input.read_text())
    )
    data, pool = inspect(record, args.seed, args.roof_type)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    for i, candidate in enumerate(pool.valid):
        args.output.with_name(args.output.stem + f"-candidate-{i}.svg").write_text(
            svg(candidate.architecture.decomposition, candidate.composition)
        )
    print(
        json.dumps(
            {
                "status": data["status"],
                "valid": len(pool.valid),
                "rejected": len(pool.rejected),
                "selected": data["selected"],
            }
        )
    )


if __name__ == "__main__":
    main()
