"""Final mesh smoke, UV/material editability, saved scenes and review renders.

blender -b --factory-startup --python-exit-code 1 --python <this script> -- --output-dir python/out/acceptance
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
DEPENDENCIES = (
    SCRIPT_DIR / ".roof-deps" / f"cp{sys.version_info.major}{sys.version_info.minor}"
)
if DEPENDENCIES.is_dir():
    sys.path.insert(0, str(DEPENDENCIES))
from blender_generate_roof_from_footprint import generate_object
from roof_generator.core.roof_geometry import UnsupportedRoofError


def validate_blender_object(obj, direction):
    import bmesh
    from mathutils import Vector

    mesh = obj.data
    if mesh.validate(verbose=True, clean_customdata=False):
        raise AssertionError("Blender detected invalid final mesh data")
    bm = bmesh.new()
    bm.from_mesh(mesh)
    try:
        assert not any(
            e.is_wire or (not e.is_boundary and not e.is_manifold) for e in bm.edges
        )
        assert all(v.is_manifold for v in bm.verts)
        assert all(face.calc_area() > 1e-8 for face in bm.faces)
        assert all(face.normal.dot(Vector(direction)) > 0 for face in bm.faces)
        errors = []
        for face in bm.faces:
            p = np.asarray([tuple(v.co) for v in face.verts], float)
            p -= p[0]
            _, _, vh = np.linalg.svd(p - p.mean(axis=0), full_matrices=True)
            errors.append(float(max(abs(p @ vh[-1]))))
        assert max(errors) < 2e-5, errors
    finally:
        bm.free()
    assert mesh.uv_layers.active is not None
    assert len(mesh.materials) > 0
    return max(errors)


def unwrap(obj):
    import bpy

    for old in bpy.context.selected_objects:
        old.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    result = bpy.ops.uv.smart_project(island_margin=0.03)
    assert "FINISHED" in result
    bpy.ops.object.mode_set(mode="OBJECT")
    assert any(abs(x.uv.x) + abs(x.uv.y) > 0 for x in obj.data.uv_layers.active.data)


def source_object(
    bpy, name, points, location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)
):
    mesh = bpy.data.meshes.new(name + "_footprint")
    mesh.from_pydata(
        [(float(x), float(y), 0) for x, y in points], [], [list(range(len(points)))]
    )
    mesh.update()
    obj = bpy.data.objects.new(name + "_source", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = rotation
    obj.scale = scale
    bpy.context.view_layer.update()
    return obj


def add_building_base(bpy, name, roof):
    # Render context only: these walls are a separate object, never part of the
    # final roof mesh. In particular no underside is added to the roof.
    from collections import Counter

    incidence = Counter(
        tuple(sorted((a, b)))
        for face in roof.faces
        for a, b in zip(face, face[1:] + face[:1])
    )
    perimeter = [edge for edge, count in incidence.items() if count == 1]
    mesh = bpy.data.meshes.new(name + "_walls")
    verts = []
    faces = []
    for a, b in perimeter:
        pa, pb = roof.vertices[a], roof.vertices[b]
        i = len(verts)
        verts.extend([(pa[0], pa[1], -3.2), (pb[0], pb[1], -3.2), pb, pa])
        faces.append((i, i + 1, i + 2, i + 3))
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name + "_walls", mesh)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.new(name + "_wall_mat")
    mat.diffuse_color = (0.72, 0.70, 0.63, 1)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs[
        "Base Color"
    ].default_value = mat.diffuse_color
    obj.data.materials.append(mat)
    return obj


def render_case(bpy, case, out):
    from mathutils import Vector

    for old in list(bpy.data.objects):
        bpy.data.objects.remove(old, do_unlink=True)
    p = case["footprint"]
    src = source_object(bpy, case["name"], p)
    obj, result = generate_object(
        src, roof_type=case["roof_type"], pitch=case["pitch"], debug_parts=False
    )
    src.hide_render = True
    src.hide_set(True)
    from dataclasses import replace

    world = np.asarray(result.spec.vertices) + result.spec.location
    add_building_base(
        bpy, case["name"], replace(result.roof.mesh, vertices=tuple(map(tuple, world)))
    )
    bounds = np.asarray([tuple(v.co) for v in obj.data.vertices], float) + np.asarray(
        obj.location
    )
    center = (bounds.min(axis=0) + bounds.max(axis=0)) / 2
    span = max(np.ptp(bounds[:, 0]), np.ptp(bounds[:, 1]), 1.0)
    bpy.ops.object.camera_add(
        location=tuple(center + np.array([span * 0.85, -span * 1.0, span * 0.95]))
    )
    camera = bpy.context.object
    direction = Vector(tuple(center - np.array(camera.location)))
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = span * 1.65
    bpy.context.scene.camera = camera
    bpy.ops.object.light_add(
        type="AREA",
        location=tuple(center + np.array([-span * 0.3, -span * 0.5, span * 1.5])),
    )
    bpy.context.object.data.energy = 2000
    bpy.context.object.data.shape = "DISK"
    bpy.context.object.data.size = span
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 700
    scene.render.resolution_percentage = 100
    scene.world.color = (0.4, 0.4, 0.4)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(out / f"{case['name']}.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{case['name']}.blend"))
    bpy.ops.render.render(write_still=True)


def main():
    import bpy

    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="python/out/acceptance")
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args(argv)
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    cases = json.loads(
        (SCRIPT_DIR / "tests" / "fixtures" / "roof_acceptance.json").read_text()
    )
    results = []
    for i, case in enumerate(cases):
        source = source_object(
            bpy,
            case["name"],
            case["footprint"],
            location=((i % 4) * 27, (i // 4) * 23, 3.2),
        )
        obj, result = generate_object(
            source, roof_type=case["roof_type"], pitch=case["pitch"]
        )
        unwrap(obj)
        error = validate_blender_object(obj, result.frame.axis_n)
        assert len(result.roof.decomposition.parts) == case["expected_parts"]
        for tag in case["features"]:
            assert result.roof.validation.features.get(tag, 0) > 0
        source.hide_set(True)
        row = {
            "name": case["name"],
            "status": "ok",
            "parts": len(result.roof.decomposition.parts),
            "faces": len(obj.data.polygons),
            "vertices": len(obj.data.vertices),
            "max_planarity_error_blender": error,
            "features": result.roof.validation.features,
        }
        results.append(row)
        print(json.dumps(row), flush=True)
    # Applied world translation, yaw, tilt and nonuniform object scale. This
    # tests the actual Blender source-object reader and direction hint.
    case = next(c for c in cases if c["name"] == "orthogonal_L")
    src = source_object(
        bpy,
        "object_transform",
        case["footprint"],
        location=(95, 110, 7.2),
        rotation=(0.18, 0.25, 0.47),
        scale=(1.2, 0.85, 1),
    )
    obj, result = generate_object(src)
    unwrap(obj)
    validate_blender_object(obj, result.frame.axis_n)
    results.append(
        {"name": "object_transform", "status": "ok", "faces": len(obj.data.polygons)}
    )
    src = source_object(
        bpy,
        "far_translation",
        case["footprint"],
        location=(1e6, -1e6, 12),
        rotation=(0.18, 0.25, 0.47),
    )
    obj, result = generate_object(src)
    validate_blender_object(obj, result.frame.axis_n)
    assert max(abs(float(x)) for v in obj.data.vertices for x in v.co) < 100
    assert np.allclose(obj.location, src.matrix_world.translation, atol=0, rtol=0)
    results.append(
        {"name": "far_translation", "status": "ok", "faces": len(obj.data.polygons)}
    )
    # An ordinary gridded plane also travels through boundary extraction.
    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=5, y_subdivisions=4, size=2, location=(130, 110, 4)
    )
    src = bpy.context.object
    src.name = "gridded_rectangle"
    src.scale = (6, 3, 1)
    bpy.context.view_layer.update()
    obj, result = generate_object(src, roof_type="hip")
    unwrap(obj)
    validate_blender_object(obj, result.frame.axis_n)
    results.append(
        {"name": "gridded_source", "status": "ok", "faces": len(obj.data.polygons)}
    )
    # Invalid/nonplanar source must fail without creating any output object.
    src = source_object(bpy, "invalid_source", [(0, 0), (12, 0), (12, 6), (0, 6)])
    src.data.vertices[1].co.z = 2
    src.data.update()
    bpy.context.view_layer.update()
    before = set(bpy.data.objects)
    try:
        generate_object(src)
    except UnsupportedRoofError:
        pass
    else:
        raise AssertionError("nonplanar source was accepted")
    assert set(bpy.data.objects) == before
    bpy.data.objects.remove(src, do_unlink=True)
    # The same CLI entry used by existing users routes explicitly to final
    # generation when --roof-kind is provided.
    src = source_object(
        bpy, "cli_source", [(0, 0), (12, 0), (12, 6), (0, 6)], location=(160, 110, 4)
    )
    bpy.context.view_layer.objects.active = src
    from blender_generate_roof_from_mesh import main as mesh_entry

    saved = sys.argv[:]
    try:
        sys.argv = [
            "blender",
            "--",
            "--object-name",
            src.name,
            "--roof-kind",
            "hip",
            "--mesh-name",
            "cli_final_roof",
        ]
        assert mesh_entry() == 0
        validate_blender_object(bpy.data.objects["cli_final_roof"], (0, 0, 1))
    finally:
        sys.argv = saved
    results.append({"name": "existing_cli_final_path", "status": "ok"})
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "all_roofs.blend"))
    (out / "blender_report.json").write_text(json.dumps(results, indent=2) + "\n")
    if not args.no_render:
        for name in [
            "orthogonal_L",
            "orthogonal_T",
            "orthogonal_U",
            "oblique_L",
            "general_convex_quad",
            "residential_multi_reflex",
        ]:
            render_case(bpy, next(c for c in cases if c["name"] == name), out)
    print("FINAL_ROOF_SMOKE_OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
