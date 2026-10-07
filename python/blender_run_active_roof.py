from __future__ import annotations

import importlib
from pathlib import Path
import sys


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
    "blender_adapter",
    "blender_import_roof_result",
    "blender_generate_roof_from_mesh",
)

from blender_adapter import solve_planar_mesh_to_mesh_specs
from blender_adapter import summarize_single_primitive_preview_input
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
from blender_roof_graph_props import store_roof_graph_metadata
from blender_roof_solver_props import read_solver_config
from blender_roof_solver_props import resolve_solver_config


OBJECT_NAME = None
MESH_NAME = "roof"
ROOF_HEIGHT = 25.0
LAMBDA_WEIGHT = 0.1
FIXED_ROOF_VERTEX_ID = None
SEPARATION_FACTOR = 1.25
REPLACE_OUTPUT = True


def main() -> int:
    import bpy

    source_object = resolve_source_object(bpy, OBJECT_NAME)
    vertices_world, faces = extract_object_mesh(source_object)
    primal_faces = extract_explicit_primal_faces(source_object)
    boundary_edge_roles, boundary_role_source = extract_boundary_edge_roles_with_source(source_object)
    preview_input_summary = summarize_single_primitive_preview_input(vertices_world, faces)
    mesh_debug_summary = describe_mesh_input(
        source_object,
        boundary_edge_roles=boundary_edge_roles,
        primal_faces=primal_faces,
        boundary_role_source=boundary_role_source,
    )
    solver_config = resolve_solver_config(
        overrides={
            "mesh_name": MESH_NAME,
            "roof_height": ROOF_HEIGHT,
            "lambda_weight": LAMBDA_WEIGHT,
            "fixed_roof_vertex_id": FIXED_ROOF_VERTEX_ID,
            "separation_factor": SEPARATION_FACTOR,
        },
        stored_config=read_solver_config(source_object),
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
        preview_hint = ""
        if not primal_faces and not boundary_edge_roles and "primitive_kind=residual" in preview_input_summary:
            preview_hint = (
                "Preview hint: this boundary-only outline is residual. For a low-friction visual check, run "
                "blender_preview_active_single_primitive_roof.py with ROOF_KIND = 'flat' (orthogonal residual "
                "outline) or ROOF_KIND = 'gable' (orthogonal grid outline). "
                "Strict paper-aligned mode still requires explicit roof topology or authored roof_role_i input.\n\n"
            )
        raise ValueError(
            f"Failed to build a roof from '{source_object.name}'.\n"
            f"Input summary: {summarize_planar_input(vertices_world, primal_faces if primal_faces is not None else faces)}\n"
            f"Preview summary: {preview_input_summary}\n"
            f"Mesh debug: {mesh_debug_summary}\n\n"
            f"{preview_hint}"
            f"{SUPPORTED_INPUT_MESSAGE}\n\n"
            f"Original error: {exc}"
        ) from exc

    collection = ensure_collection(bpy, f"{solver_config['mesh_name']}_comparison")
    if REPLACE_OUTPUT:
        remove_collection_objects(bpy, collection)

    for mesh_spec in mesh_specs:
        obj = create_mesh_object(bpy, mesh_spec, collection)
        store_roof_graph_metadata(obj, payload["faces"], solver_config)
        assign_material(bpy, obj, mesh_spec.color)

    print(summarize_result(payload))
    return 0


if __name__ == "__main__":
    main()
