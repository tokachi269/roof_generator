from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.roof_graph_io import read_primal_roof_graph
from core.roof_runner import solve_primal_roof_graph


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Optimize a primal roof graph and emit JSON output.")
    parser.add_argument("input_base_path", help="Base path without extension for .verts/.faces files")
    parser.add_argument("--output", required=True, help="Path to the output JSON file")
    parser.add_argument("--roof-height", type=float, default=50.0, help="Initial z height for roof vertices")
    parser.add_argument("--lambda-weight", type=float, default=0.0, help="XY regularization weight")
    parser.add_argument("--fixed-roof-vertex-id", type=int, default=None, help="Optional fixed roof vertex id")
    return parser


def main() -> int:
    args = build_argument_parser().parse_args()
    vertices_2d, faces = read_primal_roof_graph(args.input_base_path)
    result = solve_primal_roof_graph(
        vertices_2d,
        faces,
        roof_height=args.roof_height,
        lambda_weight=args.lambda_weight,
        fixed_roof_vertex_id=args.fixed_roof_vertex_id,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result.to_json_dict(), indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())