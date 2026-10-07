# Deprecated legacy preview: use blender_generate_roof_from_footprint.py for final roofs.
from __future__ import annotations

import importlib
import json
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
    "blender_generate_roof_from_mesh",
)

from blender_generate_roof_from_mesh import extract_object_mesh
from blender_adapter import solve_planar_mesh_with_role_preset_to_mesh_specs
from blender_adapter import summarize_single_primitive_preview_input


def main() -> int:
    import bpy

    _clear_scene(bpy)
    cases = [
        _create_rectangle_object_case(bpy),
        _create_gridded_rectangle_object_case(bpy),
        _create_l_shaped_grid_object_case(bpy),
        _create_l_shaped_grid_object_case(bpy, name="l_shaped_grid_gable", roof_kind="gable"),
        _create_t_shaped_grid_object_case(bpy),
        _create_reported_complex_grid_object_case(bpy),
    ]

    results = []
    for case in cases:
        vertices_world, faces = extract_object_mesh(case["object"])
        preview_summary = summarize_single_primitive_preview_input(vertices_world, faces)
        try:
            mesh_specs, payload, _frame = solve_planar_mesh_with_role_preset_to_mesh_specs(
                vertices_world,
                faces,
                roof_kind=case["roof_kind"],
                mesh_name=case["name"],
                roof_height=3.0,
                lambda_weight=0.0,
                separation_factor=1.0,
                gable_pair_mode="shorter",
            )
            results.append(
                {
                    "name": case["name"],
                    "status": "ok",
                    "preview_summary": preview_summary,
                    "mesh_specs": len(mesh_specs),
                    "faces": len(payload["faces"]),
                    "optimized_vertices": len(payload["optimized_vertices"]),
                    "planarity_before": payload["planarity_before"],
                    "planarity_after": payload["planarity_after"],
                    "optimizer_success": payload["optimizer_success"],
                    "optimizer_message": payload["optimizer_message"],
                }
            )
        except Exception as exc:
            results.append(
                {
                    "name": case["name"],
                    "status": "error",
                    "preview_summary": preview_summary,
                    "error": str(exc),
                }
            )

    print(json.dumps(results, indent=2))
    return 0


def _clear_scene(bpy) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def _create_rectangle_object_case(bpy) -> dict:
    bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0.0, 0.0, 0.0))
    obj = bpy.context.active_object
    obj.name = "rectangle_source"
    obj.scale = (2.0, 1.0, 1.0)
    return {"name": "rectangle", "object": obj, "roof_kind": "gable"}


def _create_gridded_rectangle_object_case(bpy) -> dict:
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=3, y_subdivisions=3, size=2.0, location=(0.0, 0.0, 0.0))
    obj = bpy.context.active_object
    obj.name = "gridded_rectangle_source"
    obj.scale = (2.0, 1.0, 1.0)
    return {"name": "gridded_rectangle", "object": obj, "roof_kind": "gable"}


def _create_l_shaped_grid_object_case(bpy, name: str = "l_shaped_grid", roof_kind: str = "flat") -> dict:
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=3, y_subdivisions=3, size=2.0, location=(0.0, 0.0, 0.0))
    obj = bpy.context.active_object
    obj.name = f"{name}_source"
    obj.scale = (2.0, 1.0, 1.0)

    mesh = obj.data
    polygon_centers = []
    for polygon in mesh.polygons:
        center = sum((mesh.vertices[vertex_id].co for vertex_id in polygon.vertices), mesh.vertices[polygon.vertices[0]].co * 0.0) / len(polygon.vertices)
        polygon_centers.append((polygon.index, float(center.x + center.y)))
    polygon_to_remove = max(polygon_centers, key=lambda item: item[1])[0]
    polygons_to_keep = [polygon.index for polygon in mesh.polygons if polygon.index != polygon_to_remove]
    kept_faces = [tuple(mesh.polygons[index].vertices) for index in polygons_to_keep]
    vertices = [tuple(vertex.co) for vertex in mesh.vertices]
    new_mesh = bpy.data.meshes.new("l_shaped_grid_mesh")
    new_mesh.from_pydata(vertices, [], [list(face) for face in kept_faces])
    new_mesh.update(calc_edges=True)
    obj.data = new_mesh
    return {"name": name, "object": obj, "roof_kind": roof_kind}


def _create_t_shaped_grid_object_case(bpy) -> dict:
    vertices = [
        (0.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        (4.0, 0.0, 0.0),
        (6.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (2.0, 1.0, 0.0),
        (4.0, 1.0, 0.0),
        (6.0, 1.0, 0.0),
        (0.0, 2.0, 0.0),
        (2.0, 2.0, 0.0),
        (4.0, 2.0, 0.0),
        (6.0, 2.0, 0.0),
    ]
    faces = (
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (5, 6, 10, 9),
    )
    mesh = bpy.data.meshes.new("t_shaped_grid_mesh")
    mesh.from_pydata(vertices, [], [list(face) for face in faces])
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new("t_shaped_grid_gable_source", mesh)
    bpy.context.collection.objects.link(obj)
    return {"name": "t_shaped_grid_gable", "object": obj, "roof_kind": "gable"}


def _create_reported_complex_grid_object_case(bpy) -> dict:
    occupied_cells = {
        (0, 0),
        (1, 0),
        (2, 0),
        (3, 0),
        (0, 1),
        (1, 1),
        (2, 1),
        (3, 1),
        (4, 1),
        (1, 2),
        (3, 2),
    }
    points = sorted(
        {
            point
            for x_value, y_value in occupied_cells
            for point in (
                (x_value, y_value),
                (x_value + 1, y_value),
                (x_value + 1, y_value + 1),
                (x_value, y_value + 1),
            )
        },
        key=lambda point: (point[1], point[0]),
    )
    diagonal_basis_point = (1, 1)
    points = [points[0], diagonal_basis_point] + [
        point for point in points[1:] if point != diagonal_basis_point
    ]
    vertex_id_by_point = {point: vertex_id for vertex_id, point in enumerate(points)}
    vertices = [(x_value, y_value, 0.0) for x_value, y_value in points]
    faces = [
        (
            vertex_id_by_point[(x_value, y_value)],
            vertex_id_by_point[(x_value + 1, y_value)],
            vertex_id_by_point[(x_value + 1, y_value + 1)],
            vertex_id_by_point[(x_value, y_value + 1)],
        )
        for x_value, y_value in sorted(occupied_cells, key=lambda point: (point[1], point[0]))
    ]
    mesh = bpy.data.meshes.new("reported_complex_grid_mesh")
    mesh.from_pydata(vertices, [], [list(face) for face in faces])
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new("reported_complex_grid_gable_source", mesh)
    bpy.context.collection.objects.link(obj)
    return {"name": "reported_complex_grid_gable", "object": obj, "roof_kind": "gable"}


if __name__ == "__main__":
    main()
