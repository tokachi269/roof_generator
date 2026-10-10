# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only inspection of canonical partition, architecture and topology stages."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "addon"))
from roof_generator.core.footprint import analyze
from roof_generator.core.partition_candidates import candidates
from roof_generator.core.architecture_selection import recommend, Policy
from roof_generator.core.topology_candidates import build_candidates
from roof_generator.core.errors import UnsupportedRoofError
from python.inspect_architectural_parts import fixture
from python.roof_diagrams import svg
from roof_generator.core.polygon_generation import candidates as polygon_candidates, PolygonCandidates
from roof_generator.core.generation import GenerationSettings, uses_polygon_model


def inspect(record, seed=0, roof_type="gable"):
    fp = analyze(record["footprint"])
    if uses_polygon_model(fp,roof_type):
        pool=polygon_candidates(fp,GenerationSettings(roof_type,seed=seed))
        output={'input':record,'seed':seed,'roof_type':roof_type,
                'architecture':pool.interpretation.inspect(),'ranking':pool.inspect_ranking(),
                'valid_candidates':[{'id':c.id,'architectural_parts':c.architecture.inspect(),
                    'graph':c.graph.inspect(),'geometry_problem':asdict(c.geometry),
                    'features':c.inspect_features()} for c in pool.valid],
                'rejected':[asdict(r) for r in pool.rejected],'complete':pool.complete,
                'status':'unsupported','selected':None}
        try:
            selected=pool.select(seed);output.update(status='mesh',selected=selected.id,
                                                     selected_ends=selected.architecture.inspect()['ends'])
        except UnsupportedRoofError as exc:output['reason']=str(exc)
        return output,pool
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
        if isinstance(pool,PolygonCandidates):
            points=candidate.mesh.vertices
            colors={'ridge':'#bd203b','valley':'#2467b3','hip':'#cfaa26','eave':'#444','gable_end':'#9346b2'}
            x0=min(p[0] for p in points);x1=max(p[0] for p in points)
            y0=min(p[1] for p in points);y1=max(p[1] for p in points)
            lines=[]
            for edge in candidate.graph.edges:
                a,b=(points[v] for v in edge.vertices)
                lines.append(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="{colors[edge.kind]}"/>')
            drawing=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0-.01} {y0-.01} {x1-x0+.02} {y1-y0+.02}" width="700" height="700"><g stroke-width="0.002">'+''.join(lines)+'</g></svg>'
            args.output.with_name(args.output.stem+f'-candidate-{i}.svg').write_text(drawing)
            continue
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
