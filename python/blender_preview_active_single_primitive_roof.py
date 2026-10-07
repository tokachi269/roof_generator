# Deprecated legacy preview: use blender_generate_roof_from_footprint.py for final roofs.
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


OBJECT_NAME = None
ROOF_KIND = "gable"
GABLE_PAIR_MODE = "shorter"
MESH_NAME = "preview_roof"
ROOF_HEIGHT = 3.0
LAMBDA_WEIGHT = 0.0
FIXED_ROOF_VERTEX_ID = None
SEPARATION_FACTOR = 1.25
REPLACE_OUTPUT = True


def main() -> int:
    import bpy

    source_object = resolve_source_object(bpy, OBJECT_NAME)
    vertices_world, faces = extract_object_mesh(source_object)
    preview_input_summary = summarize_single_primitive_preview_input(vertices_world, faces)
    try:
        mesh_specs, payload, _frame = solve_planar_mesh_with_role_preset_to_mesh_specs(
            vertices_world,
            faces,
            roof_kind=ROOF_KIND,
            mesh_name=MESH_NAME,
            roof_height=ROOF_HEIGHT,
            lambda_weight=LAMBDA_WEIGHT,
            fixed_roof_vertex_id=FIXED_ROOF_VERTEX_ID,
            separation_factor=SEPARATION_FACTOR,
            gable_pair_mode=GABLE_PAIR_MODE,
        )
    except Exception as exc:
        preview_hint = ""
        if "primitive_kind=residual" in preview_input_summary:
            preview_hint = (
                "Preview hint: this outline is residual. The current preview path supports ROOF_KIND = 'flat' for "
                "orthogonal residual outlines; ROOF_KIND = 'gable' is also supported for orthogonal grid outlines.\n\n"
            )
        raise ValueError(
            f"Failed to preview a single primitive roof from '{source_object.name}'.\n"
            f"Input summary: {summarize_planar_input(vertices_world, faces)}\n\n"
            f"Preview summary: {preview_input_summary}\n\n"
            f"{preview_hint}"
            f"{SUPPORTED_PREVIEW_MESSAGE}\n\n"
            f"Original error: {exc}"
        ) from exc

    collection_name = f"{MESH_NAME}_comparison"
    collection = ensure_collection(bpy, collection_name)
    if REPLACE_OUTPUT:
        remove_collection_objects(bpy, collection)

    for mesh_spec in mesh_specs:
        obj = create_mesh_object(bpy, mesh_spec, collection)
        assign_material(bpy, obj, mesh_spec.color)

    print(summarize_result(payload))
    return 0


if __name__ == "__main__":
    main()
