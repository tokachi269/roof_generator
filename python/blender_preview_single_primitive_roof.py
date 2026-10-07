# Deprecated legacy preview: use blender_generate_roof_from_footprint.py for final roofs.
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
        if (candidate / "blender_adapter.py").is_file() and candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
            return


_configure_script_path()


def _reload_local_modules(*module_names: str) -> None:
    for module_name in module_names:
        module = importlib.import_module(module_name)
        importlib.reload(module)


_reload_local_modules(
    "core.roof_topology",
    "core.roof_graph_io",
    "core.roof_core",
    "core.roof_pipeline",
    "core.roof_runner",
    "core.roof_topology_generator",
    "core.roof_topology_adapter",
    "blender_adapter",
    "blender_import_roof_result",
    "blender_generate_roof_from_mesh",
)

from blender_adapter import solve_planar_mesh_with_role_preset_to_mesh_specs
from blender_adapter import summarize_single_primitive_preview_input
from blender_adapter import summarize_planar_input
from blender_adapter import summarize_result
from blender_adapter import SUPPORTED_PREVIEW_MESSAGE
from blender_generate_roof_from_mesh import extract_object_mesh
from blender_generate_roof_from_mesh import remove_collection_objects
from blender_generate_roof_from_mesh import resolve_source_object
from blender_import_roof_result import assign_material
from blender_import_roof_result import create_mesh_object
from blender_import_roof_result import ensure_collection


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quick preview for a single primitive roof without authoring roof_role_i first.")
    parser.add_argument("--object-name", default=None, help="Source Blender mesh object name. Defaults to the active object.")
    parser.add_argument("--roof-kind", choices=("flat", "gable"), default="gable", help="Single primitive preview roof kind")
    parser.add_argument("--gable-pair-mode", choices=("shorter", "longer"), default="shorter", help="Choose which opposite edge pair becomes gable_end for gable preview")
    parser.add_argument("--mesh-name", default="preview_roof", help="Base name for generated result objects")
    parser.add_argument("--roof-height", type=float, default=3.0, help="Initial z height for roof vertices in local plane space")
    parser.add_argument("--lambda-weight", type=float, default=0.0, help="XY regularization weight")
    parser.add_argument("--fixed-roof-vertex-id", type=int, default=None, help="Optional fixed roof vertex id")
    parser.add_argument("--separation-factor", type=float, default=1.25, help="Horizontal spacing factor between initial and optimized meshes")
    parser.add_argument("--replace-output", action="store_true", help="Delete existing generated result objects before adding new ones")
    return parser


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = build_argument_parser().parse_args(argv)

    import bpy

    source_object = resolve_source_object(bpy, args.object_name)
    vertices_world, faces = extract_object_mesh(source_object)
    preview_input_summary = summarize_single_primitive_preview_input(vertices_world, faces)
    try:
        mesh_specs, payload, _frame = solve_planar_mesh_with_role_preset_to_mesh_specs(
            vertices_world,
            faces,
            roof_kind=args.roof_kind,
            mesh_name=args.mesh_name,
            roof_height=args.roof_height,
            lambda_weight=args.lambda_weight,
            fixed_roof_vertex_id=args.fixed_roof_vertex_id,
            separation_factor=args.separation_factor,
            gable_pair_mode=args.gable_pair_mode,
        )
    except Exception as exc:
        raise ValueError(
            f"Failed to preview a single primitive roof from '{source_object.name}'.\n"
            f"Input summary: {summarize_planar_input(vertices_world, faces)}\n\n"
            f"Preview summary: {preview_input_summary}\n\n"
            f"{SUPPORTED_PREVIEW_MESSAGE}\n\n"
            f"Original error: {exc}"
        ) from exc

    collection_name = f"{args.mesh_name}_comparison"
    collection = ensure_collection(bpy, collection_name)
    if args.replace_output:
        remove_collection_objects(bpy, collection)

    for mesh_spec in mesh_specs:
        obj = create_mesh_object(bpy, mesh_spec, collection)
        assign_material(bpy, obj, mesh_spec.color)

    print(summarize_result(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())