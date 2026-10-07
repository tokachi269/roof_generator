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
    "blender_adapter",
    "blender_import_roof_result",
)

from blender_adapter import solve_planar_mesh_to_mesh_specs
from blender_adapter import summarize_planar_input
from blender_adapter import summarize_result
from blender_adapter import SUPPORTED_INPUT_MESSAGE
from blender_import_roof_result import assign_material
from blender_import_roof_result import create_mesh_object
from blender_import_roof_result import ensure_collection
from blender_roof_graph_props import decode_primal_graph_faces
from blender_roof_graph_props import store_roof_graph_metadata
from blender_roof_solver_props import read_solver_config
from blender_roof_solver_props import resolve_solver_config


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Solve a roof directly from a planar Blender mesh and display it in the scene.")
    parser.add_argument("--object-name", default=None, help="Source Blender mesh object name. Defaults to the active object.")
    parser.add_argument("--mesh-name", default=None, help="Base name for generated result objects")
    parser.add_argument("--roof-height", type=float, default=None, help="Initial z height for roof vertices in local plane space")
    parser.add_argument("--lambda-weight", type=float, default=None, help="XY regularization weight")
    parser.add_argument("--fixed-roof-vertex-id", type=int, default=None, help="Optional fixed roof vertex id")
    parser.add_argument("--separation-factor", type=float, default=None, help="Horizontal spacing factor between initial and optimized meshes")
    parser.add_argument("--roof-kind", choices=["flat", "gable", "hip", "shed"], default=None, help="Generate one final roof from a footprint using the independent RoofPart path")
    parser.add_argument("--pitch", type=float, default=0.5, help="Final generator pitch, rise/run")
    parser.add_argument("--eave-height", type=float, default=0.0, help="Final generator offset along the footprint normal")
    parser.add_argument("--debug-parts", action="store_true", help="Color final roof faces by source part")
    parser.add_argument("--replace-output", action="store_true", help="Delete existing generated result objects before adding new ones")
    return parser


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = build_argument_parser().parse_args(argv)

    import bpy

    source_object = resolve_source_object(bpy, args.object_name)
    if args.roof_kind is not None:
        if any(value is not None for value in (args.roof_height, args.lambda_weight, args.fixed_roof_vertex_id, args.separation_factor)) or args.replace_output:
            raise ValueError("final --roof-kind generation uses --pitch/--eave-height; optimizer/comparison options and --replace-output do not apply")
        from blender_generate_roof_from_footprint import generate_object
        obj, result = generate_object(source_object, roof_type=args.roof_kind, pitch=args.pitch, eave_height=args.eave_height, mesh_name=args.mesh_name, debug_parts=args.debug_parts)
        print(f"Final roof: {obj.name}, parts={len(result.roof.decomposition.parts)}, faces={len(obj.data.polygons)}")
        return 0
    vertices_world, faces = extract_object_mesh(source_object)
    primal_faces = extract_explicit_primal_faces(source_object)
    boundary_edge_roles, boundary_role_source = extract_boundary_edge_roles_with_source(source_object)
    mesh_debug_summary = describe_mesh_input(
        source_object,
        boundary_edge_roles=boundary_edge_roles,
        primal_faces=primal_faces,
        boundary_role_source=boundary_role_source,
    )
    solver_config = resolve_solver_config(
        overrides={
            "mesh_name": args.mesh_name,
            "roof_height": args.roof_height,
            "lambda_weight": args.lambda_weight,
            "fixed_roof_vertex_id": args.fixed_roof_vertex_id,
            "separation_factor": args.separation_factor,
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
        raise ValueError(
            f"Failed to build a roof from '{source_object.name}'.\n"
            f"Input summary: {summarize_planar_input(vertices_world, primal_faces if primal_faces is not None else faces)}\n"
            f"Mesh debug: {mesh_debug_summary}\n\n"
            f"{SUPPORTED_INPUT_MESSAGE}\n\n"
            f"Original error: {exc}"
        ) from exc

    collection_name = f"{solver_config['mesh_name']}_comparison"
    collection = ensure_collection(bpy, collection_name)
    if args.replace_output:
        remove_collection_objects(bpy, collection)

    for mesh_spec in mesh_specs:
        obj = create_mesh_object(bpy, mesh_spec, collection)
        store_roof_graph_metadata(obj, payload["faces"], solver_config)
        assign_material(bpy, obj, mesh_spec.color)

    print(summarize_result(payload))
    return 0


def resolve_source_object(bpy, object_name: str | None):
    if object_name:
        source_object = bpy.data.objects.get(object_name)
        if source_object is None:
            raise ValueError(f"could not find object '{object_name}'")
    else:
        source_object = bpy.context.view_layer.objects.active
        if source_object is None:
            raise ValueError("no active object found")
    if source_object.type != "MESH":
        raise ValueError("source object must be a mesh")
    return source_object


def extract_object_mesh(source_object):
    mesh, world_matrix, cleanup, _mesh_source = _resolve_mesh_read_view(source_object)
    try:
        vertices_world = [_vertex_world_coordinates(world_matrix, vertex.co) for vertex in mesh.vertices]
        faces = [tuple(polygon.vertices) for polygon in mesh.polygons]
        if not faces:
            raise ValueError("source mesh must contain at least one face")
        return vertices_world, faces
    finally:
        cleanup()


def extract_explicit_primal_faces(source_object):
    raw_faces = source_object.get("roof_graph_faces")
    if raw_faces is None:
        raw_faces = source_object.data.get("roof_graph_faces")
    return decode_primal_graph_faces(raw_faces)


def extract_boundary_edge_roles(source_object):
    boundary_edge_roles, _role_source = extract_boundary_edge_roles_with_source(source_object)
    return boundary_edge_roles


def extract_boundary_edge_roles_with_source(source_object):
    mesh, _world_matrix, cleanup, mesh_source = _resolve_mesh_read_view(source_object)
    try:
        boundary_edge_roles = _extract_boundary_edge_roles_from_mesh(mesh)
        if boundary_edge_roles is not None:
            return boundary_edge_roles, mesh_source
        if mesh_source != "evaluated":
            return None, "missing"

        original_mesh = getattr(source_object, "data", None)
        if original_mesh is None:
            return None, "missing"
        original_roles = _extract_boundary_edge_roles_from_mesh(original_mesh)
        if original_roles is None:
            return None, "missing"
        if not _mesh_topology_matches(mesh, original_mesh):
            return None, "missing"
        return original_roles, "original-fallback"
    finally:
        cleanup()


def describe_mesh_input(source_object, boundary_edge_roles=None, primal_faces=None, boundary_role_source: str | None = None) -> str:
    mesh, _world_matrix, cleanup, mesh_source = _resolve_mesh_read_view(source_object)
    try:
        vertex_count = len(getattr(mesh, "vertices", ()))
        face_count = len(getattr(mesh, "polygons", ()))
        evaluated_info = _mesh_role_debug_info(mesh)
        original_mesh = getattr(source_object, "data", None)
        original_info = _mesh_role_debug_info(original_mesh)
        if boundary_edge_roles is None or boundary_role_source is None:
            boundary_edge_roles, boundary_role_source = extract_boundary_edge_roles_with_source(source_object)
        role_edge_count = 0 if boundary_edge_roles is None else len(boundary_edge_roles)
        explicit_face_count = 0 if primal_faces is None else len(primal_faces)
        return (
            f"mesh_source={mesh_source}, "
            f"vertices={vertex_count}, "
            f"faces={face_count}, "
            f"evaluated_roof_role_i={evaluated_info['presence']}, "
            f"evaluated_nonzero_role_edges={evaluated_info['nonzero_count']}, "
            f"original_roof_role_i={original_info['presence']}, "
            f"original_nonzero_role_edges={original_info['nonzero_count']}, "
            f"selected_role_source={boundary_role_source}, "
            f"selected_nonzero_role_edges={role_edge_count}, "
            f"explicit_primal_faces={explicit_face_count}"
        )
    finally:
        cleanup()


def _extract_boundary_edge_roles_from_mesh(mesh):
    attributes = getattr(mesh, "attributes", None)
    if attributes is None:
        return None

    role_attribute = attributes.get("roof_role_i")
    if role_attribute is None:
        return None

    boundary_edge_roles = {}
    for edge in getattr(mesh, "edges", ()):
        role_value = int(role_attribute.data[edge.index].value)
        if role_value == 0:
            continue
        boundary_edge_roles[tuple(sorted(int(vertex_id) for vertex_id in edge.vertices))] = role_value
    return boundary_edge_roles or None


def _mesh_role_debug_info(mesh) -> dict[str, object]:
    if mesh is None:
        return {"presence": "missing", "nonzero_count": 0}
    attributes = getattr(mesh, "attributes", None)
    if attributes is None:
        return {"presence": "missing", "nonzero_count": 0}
    role_attribute = attributes.get("roof_role_i")
    if role_attribute is None:
        return {"presence": "missing", "nonzero_count": 0}
    nonzero_count = 0
    for edge in getattr(mesh, "edges", ()):
        if int(role_attribute.data[edge.index].value) != 0:
            nonzero_count += 1
    return {"presence": "present", "nonzero_count": nonzero_count}


def _mesh_topology_matches(mesh0, mesh1) -> bool:
    if mesh0 is None or mesh1 is None:
        return False
    if len(getattr(mesh0, "vertices", ())) != len(getattr(mesh1, "vertices", ())):
        return False
    if len(getattr(mesh0, "edges", ())) != len(getattr(mesh1, "edges", ())):
        return False
    if len(getattr(mesh0, "polygons", ())) != len(getattr(mesh1, "polygons", ())):
        return False
    edges0 = [tuple(sorted(int(vertex_id) for vertex_id in edge.vertices)) for edge in getattr(mesh0, "edges", ())]
    edges1 = [tuple(sorted(int(vertex_id) for vertex_id in edge.vertices)) for edge in getattr(mesh1, "edges", ())]
    return edges0 == edges1


def _resolve_mesh_read_view(source_object):
    world_matrix = getattr(source_object, "matrix_world", None)
    mesh = source_object.data
    cleanup = lambda: None
    mesh_source = "original"

    evaluated_get = getattr(source_object, "evaluated_get", None)
    if not callable(evaluated_get):
        return mesh, world_matrix, cleanup, mesh_source

    depsgraph = _try_get_depsgraph()
    try:
        evaluated_object = evaluated_get(depsgraph)
        to_mesh = getattr(evaluated_object, "to_mesh", None)
        if not callable(to_mesh):
            return mesh, world_matrix, cleanup, mesh_source
        try:
            evaluated_mesh = to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        except TypeError:
            evaluated_mesh = to_mesh()
        if evaluated_mesh is None:
            return mesh, world_matrix, cleanup, mesh_source

        world_matrix = getattr(evaluated_object, "matrix_world", world_matrix)
        mesh = evaluated_mesh
        mesh_source = "evaluated"
        clear_mesh = getattr(evaluated_object, "to_mesh_clear", None)
        if callable(clear_mesh):
            cleanup = clear_mesh
        return mesh, world_matrix, cleanup, mesh_source
    except Exception:
        return mesh, world_matrix, cleanup, mesh_source


def _try_get_depsgraph():
    try:
        import bpy  # type: ignore

        return bpy.context.evaluated_depsgraph_get()
    except Exception:
        return None


def _vertex_world_coordinates(world_matrix, coordinate) -> tuple[float, float, float]:
    if world_matrix is None:
        return tuple(float(value) for value in coordinate)
    return tuple((world_matrix @ coordinate).to_tuple())


def remove_collection_objects(bpy, collection) -> None:
    for obj in list(collection.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


if __name__ == "__main__":
    raise SystemExit(main())