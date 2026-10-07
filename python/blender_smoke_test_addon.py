# SPDX-License-Identifier: GPL-3.0-or-later
"""Install the distribution ZIP and exercise the real conversion operator.

blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_addon.py -- --zip dist/roof_generator-1.0.0.zip
"""

import argparse
import json
from pathlib import Path
import shutil
import sys
import bpy
import bmesh
import numpy as np


def validate(obj, direction=(0, 0, 1)):
    assert not obj.data.validate(verbose=True, clean_customdata=False)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    try:
        assert all(not e.is_wire and (e.is_boundary or e.is_manifold) for e in bm.edges)
        assert all(v.is_manifold for v in bm.verts)
        assert all(f.calc_area() > 1e-8 for f in bm.faces)
        errors = []
        for face in bm.faces:
            p = np.array([tuple(v.co) for v in face.verts])
            _, _, basis = np.linalg.svd(p - p.mean(axis=0), full_matrices=True)
            errors.append(float(np.max(np.abs((p - p[0]) @ basis[-1]))))
            assert np.dot(face.normal, direction) > 0
        assert max(errors) < 2e-5
    finally:
        bm.free()
    assert obj.data.materials and obj.data.uv_layers.active
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    assert bpy.ops.uv.smart_project(island_margin=0.03) == {"FINISHED"}
    bpy.ops.object.mode_set(mode="OBJECT")
    assert any(abs(u.uv.x) + abs(u.uv.y) > 0 for u in obj.data.uv_layers.active.data)
    return max(errors)


def source(name, points, location=(0, 0, 0)):
    data = bpy.data.meshes.new(name + "_footprint")
    data.from_pydata([(x, y, 0) for x, y in points], [], [list(range(len(points)))])
    obj = bpy.data.objects.new(name + "_source", data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    for old in bpy.context.selected_objects:
        old.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.view_layer.update()
    return obj


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True)
    parser.add_argument("--host-python", default=shutil.which("python3"))
    parser.add_argument("--output-dir", default="python/out/addon")
    args = parser.parse_args(argv)
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    assert bpy.ops.preferences.addon_install(
        filepath=str(Path(args.zip).resolve()), overwrite=True
    ) == {"FINISHED"}
    assert bpy.ops.preferences.addon_enable(module="roof_generator") == {"FINISHED"}
    import roof_generator

    installed = Path(roof_generator.__file__).resolve()
    assert "addons" in installed.parts
    prefs = bpy.context.preferences.addons["roof_generator"].preferences
    prefs.python_executable = args.host_python
    assert bpy.ops.roof_generator.install_dependency() == {"FINISHED"}
    from roof_generator.ui import dependency_available

    assert dependency_available()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    fixtures = json.loads(
        (Path(__file__).parent / "tests/fixtures/roof_acceptance.json").read_text()
    )
    settings = bpy.context.scene.roof_generator
    rows = []
    codes = {"ridge": 1, "hip": 2, "valley": 3}
    for i, case in enumerate(fixtures):
        src = source(
            case["name"], case["footprint"], ((i % 4) * 27, (i // 4) * 23, 3.2)
        )
        settings.roof_type = case["roof_type"]
        settings.pitch = case["pitch"]
        settings.debug_parts = True
        settings.hide_source = True
        assert bpy.ops.roof_generator.generate() == {"FINISHED"}
        obj = bpy.context.active_object
        error = validate(obj)
        assert obj != src and src.hide_get() and src.hide_render
        assert len(json.loads(obj["roof_parts"])) == case["expected_parts"]
        values = {a.value for a in obj.data.attributes["roof_feature_i"].data}
        assert all(codes[tag] in values for tag in case["features"])
        rows.append(
            {"case": case["name"], "faces": len(obj.data.polygons), "error": error}
        )
    settings.debug_parts = False
    settings.hide_source = False
    for kind in ("flat", "gable", "hip", "shed"):
        src = source(
            "type_" + kind, [(0, 0), (12.8, 0), (12.8, 7.2), (0, 7.2)], (120, 0, 3)
        )
        settings.roof_type = kind
        assert bpy.ops.roof_generator.generate() == {"FINISHED"}
        validate(bpy.context.active_object)
        assert not src.hide_get() and not src.hide_render
    src = source("transform", fixtures[7]["footprint"], (1e6, -1e6, 12))
    src.rotation_euler = (0.18, 0.25, 0.47)
    src.scale = (1.2, 0.85, 1)
    bpy.context.view_layer.update()
    settings.roof_type = "gable"
    assert bpy.ops.roof_generator.generate() == {"FINISHED"}
    obj = bpy.context.active_object
    hint = np.linalg.inv(np.asarray(src.matrix_world)[:3, :3]).T @ [0, 0, 1]
    validate(obj, hint / np.linalg.norm(hint))
    assert max(abs(float(x)) for v in obj.data.vertices for x in v.co) < 100
    invalid = source("invalid", [(0, 0), (12, 0), (12, 6), (0, 6)])
    invalid.data.vertices[1].co.z = 2
    bpy.context.view_layer.update()
    before = set(bpy.data.objects)
    try:
        status = bpy.ops.roof_generator.generate()
        assert status == {"CANCELLED"}
    except RuntimeError as error:
        assert "planar" in str(error)
    assert set(bpy.data.objects) == before
    bpy.data.objects.remove(invalid, do_unlink=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "addon_roofs.blend"))
    (output / "report.json").write_text(
        json.dumps(
            {
                "installed_addon": str(installed),
                "fixtures": rows,
                "types": 4,
                "transform": "ok",
                "unsupported": "no scene mutation",
            },
            indent=2,
        )
    )
    assert bpy.ops.preferences.addon_disable(module="roof_generator") == {"FINISHED"}
    assert not hasattr(bpy.types.Scene, "roof_generator")
    assert bpy.ops.preferences.addon_enable(module="roof_generator") == {"FINISHED"}
    assert hasattr(bpy.types.Scene, "roof_generator")
    print("INSTALLED_ADDON_SMOKE_OK", flush=True)


if __name__ == "__main__":
    main()
