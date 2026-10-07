from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path


def _configure_script_path() -> None:
    candidates = []

    file_path = Path(__file__)
    candidates.append(file_path.parent)
    try:
        candidates.append(file_path.resolve().parent)
    except OSError:
        pass

    try:
        import bpy  # type: ignore

        current_name = file_path.name
        for text in bpy.data.texts:
            text_path = getattr(text, "filepath", "")
            if not text_path:
                continue
            path = Path(text_path)
            if path.name == current_name or current_name == "":
                candidates.append(path.parent)
    except Exception:
        pass

    for candidate in candidates:
        if not candidate:
            continue
        candidate_str = str(candidate)
        if (candidate / "blender_generate_roof_from_mesh.py").is_file() and candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
            return


_configure_script_path()


def _reload_local_modules(*module_names: str) -> None:
    for module_name in module_names:
        module = importlib.import_module(module_name)
        importlib.reload(module)


_reload_local_modules(
    "blender_roof_graph_props",
    "blender_roof_solver_props",
    "blender_generate_roof_from_mesh",
)

from blender_generate_roof_from_mesh import resolve_source_object
from blender_roof_graph_props import clear_primal_graph_faces
from blender_roof_graph_props import decode_primal_graph_faces
from blender_roof_graph_props import extract_polygon_faces
from blender_roof_graph_props import store_primal_graph_faces
from blender_roof_solver_props import clear_solver_config
from blender_roof_solver_props import store_solver_config


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Store explicit roof_graph_faces on a Blender mesh or object.")
    parser.add_argument("--object-name", default=None, help="Source Blender mesh object name. Defaults to the active object.")
    parser.add_argument("--store-on", choices=("object", "mesh"), default="object", help="Where to store the roof_graph_faces custom property")
    parser.add_argument("--selected-only", action="store_true", help="Use only the selected mesh polygons as the explicit roof graph faces")
    parser.add_argument("--faces-json", default=None, help="Optional JSON array of explicit primal faces to store instead of copying mesh polygons")
    parser.add_argument("--clear", action="store_true", help="Remove any existing roof_graph_faces property from the chosen target")
    parser.add_argument("--mesh-name", default=None, help="Optional stored mesh name for generated result objects")
    parser.add_argument("--roof-height", type=float, default=None, help="Optional stored initial z height for roof vertices")
    parser.add_argument("--lambda-weight", type=float, default=None, help="Optional stored XY regularization weight")
    parser.add_argument("--fixed-roof-vertex-id", type=int, default=None, help="Optional stored fixed roof vertex id")
    parser.add_argument("--separation-factor", type=float, default=None, help="Optional stored horizontal spacing factor")
    parser.add_argument("--clear-solver-config", action="store_true", help="Remove any existing roof_solver_config property from the chosen target")
    return parser


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = build_argument_parser().parse_args(argv)

    import bpy

    source_object = resolve_source_object(bpy, args.object_name)
    target = source_object if args.store_on == "object" else source_object.data

    if args.clear:
        removed = clear_primal_graph_faces(target)
        print(f"cleared={removed}, target={args.store_on}, object={source_object.name}")
        return 0

    if args.clear_solver_config:
        removed = clear_solver_config(target)
        print(f"cleared_solver_config={removed}, target={args.store_on}, object={source_object.name}")
        return 0

    solver_config = {
        "mesh_name": args.mesh_name,
        "roof_height": args.roof_height,
        "lambda_weight": args.lambda_weight,
        "fixed_roof_vertex_id": args.fixed_roof_vertex_id,
        "separation_factor": args.separation_factor,
    }
    has_solver_config = any(value is not None for value in solver_config.values())
    if has_solver_config:
        stored_config = store_solver_config(target, solver_config)
        print(f"stored_solver_config={stored_config}, target={args.store_on}, object={source_object.name}")
        return 0

    if args.faces_json is not None:
        faces = decode_primal_graph_faces(args.faces_json)
        if faces is None:
            raise ValueError("faces_json must decode to explicit primal faces")
    else:
        faces = extract_polygon_faces(source_object.data, selected_only=args.selected_only)

    stored_faces = store_primal_graph_faces(target, faces)
    print(f"stored_faces={len(stored_faces)}, target={args.store_on}, object={source_object.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())