# SPDX-License-Identifier: GPL-3.0-or-later
"""Installed ZIP operator acceptance with per-case rendered feature inspection."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from blender_smoke_test import source, validate


def render(output):
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH" and not obj.hide_render]
    points = [obj.matrix_world @ v.co for obj in meshes for v in obj.data.vertices]
    low = Vector(tuple(min(p[k] for p in points) for k in range(3)))
    high = Vector(tuple(max(p[k] for p in points) for k in range(3)))
    center, size = (low + high) / 2, (high - low).length
    bpy.ops.object.camera_add(location=center + Vector((size, -size, size * 1.5)))
    camera = bpy.context.object
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = size * 1.2
    scene = bpy.context.scene
    scene.camera = camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_cavity = True
    scene.render.resolution_x, scene.render.resolution_y = 1000, 700
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(output / "meshes.png")
    bpy.ops.render.render(write_still=True)
    scene.render.filepath = "//meshes.png"


def overlay(obj):
    colors = {1: (.8, .025, .06, 1), 2: (.9, .4, .015, 1), 3: (.025, .18, .9, 1)}
    attribute = obj.data.attributes["roof_feature_i"]
    size = max(obj.dimensions.x, obj.dimensions.y)
    for edge in obj.data.edges:
        code = attribute.data[edge.index].value
        if code not in colors:
            continue
        curve = bpy.data.curves.new(f"feature_{edge.index}", "CURVE")
        curve.dimensions = "3D"
        curve.bevel_depth = size * .002
        spline = curve.splines.new("POLY")
        spline.points.add(1)
        for item, index in zip(spline.points, edge.vertices):
            xyz = obj.matrix_world @ obj.data.vertices[index].co + Vector((0, 0, size * .001))
            item.co = (*xyz, 1)
        line = bpy.data.objects.new(curve.name, curve)
        bpy.context.scene.collection.objects.link(line)
        material = bpy.data.materials.new(curve.name)
        material.diffuse_color = colors[code]
        material.use_nodes = True
        material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = colors[code]
        curve.materials.append(material)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zip", type=Path, required=True)
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    assert bpy.ops.preferences.addon_install(filepath=str(args.zip.resolve()), overwrite=True) == {"FINISHED"}
    assert bpy.ops.preferences.addon_enable(module="roof_generator") == {"FINISHED"}
    import roof_generator
    from roof_generator import blender_output
    rows = []
    for record in json.loads(args.inputs.read_text(encoding="utf-8"))["inputs"]:
        # New scene data per case; all input is created through Blender's public API.
        for obj in tuple(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        src = source(record["name"], record["footprint"])
        if "faces" in record:
            src.data.clear_geometry()
            src.data.from_pydata(
                [(x, y, 0) for x, y in record["footprint"]], [], record["faces"]
            )
            src.data.update()
        settings = bpy.context.scene.roof_generator
        settings.roof_type = "gable"
        settings.pitch = .5
        settings.seed = record.get("seed", 0)
        settings.debug_cells = False
        settings.hide_source = True
        row = {"name": record["name"], "status": "unsupported", "image": record["name"] + "/meshes.png"}
        before = set(bpy.data.objects)
        captured = []
        prepare = blender_output._prepare
        def observe_prepare(*arguments, **keywords):
            prepared = prepare(*arguments, **keywords)
            captured.append(prepared)
            return prepared
        # Observe the real operator result. A separate XY generation can pick
        # a different candidate after Blender float32/frame conversion.
        blender_output._prepare = observe_prepare
        try:
            result = bpy.ops.roof_generator.generate()
        except RuntimeError as exc:
            result = {"CANCELLED"}
            row["reason"] = str(exc)
        finally:
            blender_output._prepare = prepare
        if result == {"FINISHED"}:
            obj = bpy.context.active_object
            validate(obj)
            row.update(status="supported", candidate=obj["roof_candidate_id"], faces=len(obj.data.polygons))
            assert len(captured) == 1
            generation = captured[0].roof.generation
            candidate = generation.selected
            assert candidate.id == row["candidate"]
            row["inspection"] = {
                "input": record, "status": "supported", "selected_candidate": candidate.id,
                "partition": generation.interpretation.search.candidates[0].inspect(),
                "partition_scope": "first minimum source for provenance; actual support authority is architecture",
                "architecture": candidate.architecture.inspect(),
                "architecture_scope": "actual installed operator preparation",
                "graph": candidate.graph.inspect(),
                "connections": [asdict(c) for c in candidate.composition.connections],
                "features": [asdict(f) for f in getattr(candidate.composition, "features", ())],
                "resolved_ends": candidate.ends.inspect() if getattr(candidate, "ends", None) else None,
                "solved_vertices": captured[0].roof.mesh.vertices,
                "solver_preserved_graph": captured[0].roof.mesh.graph is candidate.graph,
            }
            overlay(obj)
        else:
            assert set(bpy.data.objects) == before
            assert not src.hide_get()
            src.name = record["name"] + "_unsupported_footprint"
            row["atomic_failure"] = True
        output = args.output_dir / record["name"]
        output.mkdir(parents=True, exist_ok=True)
        render(output)
        bpy.ops.wm.save_as_mainfile(filepath=str((output / "inspection.blend").resolve()))
        rows.append(row)
        print("AUTHORITY_CASE", {k: v for k, v in row.items() if k != "inspection"}, flush=True)
    report = {
        "blender": bpy.app.version_string,
        "archive_sha256": hashlib.sha256(args.zip.read_bytes()).hexdigest(),
        "addon_module": Path(roof_generator.__file__).resolve().relative_to(ROOT).as_posix(),
        "image_scope": "Blender camera render of installed operator output; colored overlay reads actual mesh edge attributes",
        "cases": rows,
    }
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
