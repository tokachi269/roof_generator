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
    "core.roof_topology",
    "core.roof_graph_io",
    "core.roof_core",
    "core.roof_pipeline",
    "core.roof_runner",
    "blender_adapter",
    "blender_import_roof_result",
    "blender_generate_roof_from_mesh",
    "blender_roof_graph_props",
    "blender_roof_solver_props",
)

from blender_adapter import solve_planar_mesh_to_mesh_specs
from blender_adapter import summarize_planar_input
from blender_adapter import summarize_result
from blender_adapter import SUPPORTED_INPUT_MESSAGE
from blender_generate_roof_from_mesh import extract_explicit_primal_faces
from blender_generate_roof_from_mesh import extract_boundary_edge_roles
from blender_generate_roof_from_mesh import extract_boundary_edge_roles_with_source
from blender_generate_roof_from_mesh import extract_object_mesh
from blender_generate_roof_from_mesh import describe_mesh_input
from blender_generate_roof_from_mesh import remove_collection_objects
from blender_generate_roof_from_mesh import resolve_source_object
from blender_import_roof_result import assign_material
from blender_import_roof_result import create_mesh_object
from blender_import_roof_result import ensure_collection
from blender_roof_graph_props import extract_polygon_faces
from blender_roof_graph_props import store_roof_graph_metadata
from blender_roof_graph_props import store_primal_graph_faces
from blender_roof_solver_props import read_solver_config
from blender_roof_solver_props import resolve_solver_config
from blender_roof_solver_props import store_solver_config


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture explicit roof graph faces from a Blender mesh and solve immediately.")
    parser.add_argument("--object-name", default=None, help="Source Blender mesh object name. Defaults to the active object.")
    parser.add_argument("--store-on", choices=("object", "mesh"), default="object", help="Where to store the roof graph properties")
    parser.add_argument("--selected-only", action="store_true", help="Capture only the selected mesh polygons as explicit roof graph faces")
    parser.add_argument("--mesh-name", default=None, help="Base name for generated result objects")
    parser.add_argument("--roof-height", type=float, default=None, help="Initial z height for roof vertices in local plane space")
    parser.add_argument("--lambda-weight", type=float, default=None, help="XY regularization weight")
    parser.add_argument("--fixed-roof-vertex-id", type=int, default=None, help="Optional fixed roof vertex id")
    parser.add_argument("--separation-factor", type=float, default=None, help="Horizontal spacing factor between initial and optimized meshes")
    parser.add_argument("--replace-output", action="store_true", help="Delete existing generated result objects before adding new ones")
    return parser


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = build_argument_parser().parse_args(argv)

    import bpy

    source_object = resolve_source_object(bpy, args.object_name)
    target = source_object if args.store_on == "object" else source_object.data

    captured_faces = extract_polygon_faces(source_object.data, selected_only=args.selected_only)
    store_primal_graph_faces(target, captured_faces)

    override_config = {
        "mesh_name": args.mesh_name,
        "roof_height": args.roof_height,
        "lambda_weight": args.lambda_weight,
        "fixed_roof_vertex_id": args.fixed_roof_vertex_id,
        "separation_factor": args.separation_factor,
    }
    solver_config = resolve_solver_config(overrides=override_config, stored_config=read_solver_config(source_object))
    store_solver_config(target, solver_config)

    vertices_world, faces = extract_object_mesh(source_object)
    primal_faces = extract_explicit_primal_faces(source_object)
    boundary_edge_roles, boundary_role_source = extract_boundary_edge_roles_with_source(source_object)
    mesh_debug_summary = describe_mesh_input(
        source_object,
        boundary_edge_roles=boundary_edge_roles,
        primal_faces=primal_faces,
        boundary_role_source=boundary_role_source,
    )
    try:
        mesh_specs, payload, _frame = solve_planar_mesh_to_mesh_specs(
            vertices_world,
            faces,
            primal_faces=primal_faces,
            boundary_edge_roles=boundary_edge_roles,
            mesh_name=solver_config["mesh_name"],
            roof_height=solver_config["roof_height"],
            lambda_weight=solver_config["lambda_weight"],
            fixed_roof_vertex_id=solver_config["fixed_roof_vertex_id"],
            separation_factor=solver_config["separation_factor"],
        )
    except Exception as exc:
        raise ValueError(
            f"Failed to build a roof from '{source_object.name}'.\n"
            f"Input summary: {summarize_planar_input(vertices_world, primal_faces if primal_faces is not None else faces)}\n"
            f"Mesh debug: {mesh_debug_summary}\n\n"
            f"{SUPPORTED_INPUT_MESSAGE}\n\n"
            f"Original error: {exc}"
        ) from exc

    collection = ensure_collection(bpy, f"{solver_config['mesh_name']}_comparison")
    if args.replace_output:
        remove_collection_objects(bpy, collection)

    for mesh_spec in mesh_specs:
        obj = create_mesh_object(bpy, mesh_spec, collection)
        store_roof_graph_metadata(obj, payload["faces"], solver_config)
        assign_material(bpy, obj, mesh_spec.color)

    print(f"captured_faces={len(captured_faces)}, {summarize_result(payload)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())