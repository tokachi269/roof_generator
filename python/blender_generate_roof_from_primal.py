from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from blender_adapter import solve_primal_graph_to_mesh_specs
from blender_adapter import summarize_result
from blender_import_roof_result import assign_material
from blender_import_roof_result import clear_scene
from blender_import_roof_result import create_mesh_object
from blender_import_roof_result import ensure_collection


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Solve a primal roof graph and display the result directly in Blender.")
    parser.add_argument("input_base_path", help="Base path without extension for .verts/.faces files")
    parser.add_argument("--mesh-name", default="roof", help="Base object name to create in Blender")
    parser.add_argument("--roof-height", type=float, default=50.0, help="Initial z height for roof vertices")
    parser.add_argument("--lambda-weight", type=float, default=0.0, help="XY regularization weight")
    parser.add_argument("--fixed-roof-vertex-id", type=int, default=None, help="Optional fixed roof vertex id")
    parser.add_argument("--separation-factor", type=float, default=1.25, help="Horizontal spacing factor between initial and optimized meshes")
    parser.add_argument("--keep-scene", action="store_true", help="Do not clear the current scene before importing")
    return parser


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = build_argument_parser().parse_args(argv)

    import bpy

    mesh_specs, payload = solve_primal_graph_to_mesh_specs(
        args.input_base_path,
        mesh_name=args.mesh_name,
        roof_height=args.roof_height,
        lambda_weight=args.lambda_weight,
        fixed_roof_vertex_id=args.fixed_roof_vertex_id,
        separation_factor=args.separation_factor,
    )

    if not args.keep_scene:
        clear_scene(bpy)

    collection = ensure_collection(bpy, f"{args.mesh_name}_comparison")
    for mesh_spec in mesh_specs:
        obj = create_mesh_object(bpy, mesh_spec, collection)
        assign_material(bpy, obj, mesh_spec.color)

    print(summarize_result(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())