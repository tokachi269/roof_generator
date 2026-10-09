# SPDX-License-Identifier: GPL-3.0-or-later
"""Installed/source addon, editable meshes, seeded variation and atomic failures."""

import argparse
import json
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]


def source(name, points):
    data = bpy.data.meshes.new(name + "_footprint")
    data.from_pydata([(x, y, 0) for x, y in points], [], [list(range(len(points)))])
    obj = bpy.data.objects.new(name + "_source", data)
    bpy.context.scene.collection.objects.link(obj)
    for old in bpy.context.selected_objects:
        old.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.view_layer.update()
    return obj


def validate(obj, normal=(0, 0, 1)):
    assert not obj.data.validate(verbose=True, clean_customdata=False)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    try:
        assert all(e.is_boundary or e.is_manifold for e in bm.edges)
        assert all(v.is_manifold for v in bm.verts)
        assert all(
            f.calc_area() > 1e-8 and f.normal.dot(Vector(normal)) > 0 for f in bm.faces
        )
        assert all(
            abs((v.co - f.verts[0].co).dot(f.normal)) < 2e-5
            for f in bm.faces
            for v in f.verts
        )
    finally:
        bm.free()
    assert obj.data.materials and obj.data.uv_layers.active
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    assert bpy.ops.uv.smart_project(island_margin=0.03) == {"FINISHED"}
    bpy.ops.object.mode_set(mode="OBJECT")
    assert any(abs(p.uv.x) + abs(p.uv.y) > 0 for p in obj.data.uv_layers.active.data)
    assert obj.data.attributes.get("roof_feature_i") and obj.data.attributes.get(
        "roof_cell_i"
    )


def render(output):
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.name.endswith("_source"):
            obj.hide_render = True
    points = [
        obj.matrix_world @ vertex.co
        for obj in bpy.data.objects
        if obj.type == "MESH" and not obj.hide_render
        for vertex in obj.data.vertices
    ]
    lo = Vector(tuple(min(p[k] for p in points) for k in range(3)))
    hi = Vector(tuple(max(p[k] for p in points) for k in range(3)))
    center = (lo + hi) / 2
    extent = (hi - lo).length
    bpy.ops.object.camera_add(location=center + Vector((extent, -extent, 1.5 * extent)))
    camera = bpy.context.object
    camera.rotation_euler = (
        (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    )
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = extent * 1.2
    bpy.context.scene.camera = camera
    bpy.ops.object.light_add(type="AREA", location=center + Vector((0, 0, 40)))
    bpy.context.object.data.energy = 18000
    bpy.context.object.data.size = 60
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 64
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 700
    scene.render.resolution_percentage = 100
    scene.world.color = (0.25, 0.25, 0.25)
    scene.render.filepath = str(output / "meshes.png")
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zip", type=Path)
    p.add_argument("--output-dir", type=Path, default=ROOT / "python/out/blender")
    p.add_argument("--render", action="store_true")
    args = p.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.zip:
        assert bpy.ops.preferences.addon_install(
            filepath=str(args.zip.resolve()), overwrite=True
        ) == {"FINISHED"}
        assert bpy.ops.preferences.addon_enable(module="roof_generator") == {"FINISHED"}
    else:
        sys.path.insert(0, str(ROOT / "addon"))
        import roof_generator

        roof_generator.register()
    import roof_generator

    assert not (Path(roof_generator.__file__).parent / "dependencies.py").exists()
    from roof_generator.blender_output import generate_objects, RoofRequest
    from roof_generator.core.generation import GenerationSettings
    from roof_generator.core.errors import UnsupportedRoofError

    for obj in tuple(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    rows = []
    fixtures = [
        ("rectangle_" + kind, ((0, 0), (12, 0), (12, 6), (0, 6)), kind)
        for kind in ("gable", "hip", "shed", "flat")
    ]
    fixtures.append(
        (
            "compound_flat",
            ((0, 0), (18, 0), (18, 12), (14, 12), (14, 6), (4, 6), (4, 12), (0, 12)),
            "flat",
        )
    )
    acceptance = json.loads(
        (ROOT / "python/tests/fixtures/roof_acceptance.json").read_text()
    )
    fixtures.append(
        (
            "compound_gable_U",
            next(r["footprint"] for r in acceptance if r["name"] == "orthogonal_U"),
            "gable",
        )
    )
    fixtures.append(
        (
            "compound_gable_cross",
            (
                (0, 0),
                (6, 0),
                (6, -6),
                (10, -6),
                (10, 0),
                (16, 0),
                (16, 4),
                (10, 4),
                (10, 10),
                (6, 10),
                (6, 4),
                (0, 4),
            ),
            "gable",
        )
    )
    fixtures.append(
        (
            "mixed_branch_network",
            (
                (0, 0),
                (32, 0),
                (32, 6),
                (20, 6),
                (20, 14),
                (16, 14),
                (16, 6),
                (4, 6),
                (4, 14),
                (0, 14),
            ),
            "gable",
        )
    )
    for record in acceptance:
        if record["name"] in {"parallelogram", "trapezoid", "general_convex_quad"}:
            fixtures.append((record["name"], record["footprint"], "gable"))
        if record['name']=='residential_multi_reflex':
            fixtures.append((record['name'],record['footprint'],'gable'))
    for i, (name, points, kind) in enumerate(fixtures):
        src = source(name, points)
        # Exhibit spacing must accommodate the 32-unit branch network; source
        # geometry must not overlap another case and create render z-fighting.
        src.location = (i % 3 * 40, i // 3 * 30, 3)
        if i == 1:
            src.rotation_euler = (0.22, -0.17, 0.63)
            src.scale = (1.2, 0.8, 1.1)
        bpy.context.view_layer.update()
        settings = bpy.context.scene.roof_generator
        settings.roof_type = kind
        settings.pitch = 0.5
        settings.seed = 11
        settings.hide_source = True
        assert bpy.ops.roof_generator.generate() == {"FINISHED"}
        obj = bpy.context.active_object
        normal = src.matrix_world.to_3x3().inverted().transposed() @ Vector((0, 0, 1))
        validate(obj, normal)
        assert src.hide_get() and src.hide_render
        rows.append(
            {
                "case": name,
                "faces": len(obj.data.polygons),
                "candidate": obj["roof_candidate_id"],
                "uv": True,
                "material": True,
            }
        )
    # Real mesh variation: square gable axes, with the same source-local frame.
    square = source("square", ((0, 0), (7, 0), (7, 7), (0, 7)))
    square.location = (0, 120, 3)
    bpy.context.view_layer.update()
    ids = {}
    roof_objects = []
    for seed in range(30):
        result = generate_objects(
            (RoofRequest(square, GenerationSettings("gable", seed=seed)),),
            hide_source=False,
        )[0]
        obj, data = result
        if obj["roof_candidate_id"] not in ids:
            ids[obj["roof_candidate_id"]] = seed
            validate(obj)
            roof_objects.append(obj)
        else:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.meshes.remove(mesh)
        if len(ids) == 2:
            break
    assert len(ids) == 2
    roof_objects[1].location.x += 12
    before = set(bpy.data.objects)
    materials = set(bpy.data.materials)
    unsupported = source(
        "unsupported_compound",
        ((0,0),(12,0),(12.8,4),(4.8,4),(6,10),(2,10)),
    )
    before = set(bpy.data.objects)
    materials = set(bpy.data.materials)
    try:
        generate_objects((RoofRequest(square), RoofRequest(unsupported)))
    except UnsupportedRoofError:
        pass
    else:
        raise AssertionError("unsupported topology must fail explicitly")
    assert set(bpy.data.objects) == before and set(bpy.data.materials) == materials
    assert not unsupported.hide_get() and not unsupported.hide_render
    # CLI uses the same adapter and carries the seed into object metadata.
    import runpy

    bpy.context.view_layer.objects.active = square
    for old in bpy.context.selected_objects:
        old.select_set(False)
    square.select_set(True)
    previous = sys.argv
    try:
        sys.argv = [
            "blender",
            "--",
            "--object-name",
            square.name,
            "--seed",
            "71",
            "--roof-type",
            "hip",
        ]
        script = runpy.run_path(
            str(ROOT / "python/blender_generate_roof_from_footprint.py")
        )
        assert script["main"]() == 0
        assert bpy.context.active_object["roof_seed"] == "71"
        bpy.context.active_object.hide_render = True
    finally:
        sys.argv = previous
    unsupported.hide_render = True
    if args.render:
        render(args.output_dir)
    bpy.ops.wm.save_as_mainfile(
        filepath=str((args.output_dir / "roofs.blend").resolve())
    )
    (args.output_dir / "report.json").write_text(
        json.dumps(
            {
                "meshes": rows,
                "square_seed_variation": ids,
                "compound_failure_atomic": True,
                "cli": True,
            },
            indent=2,
        )
        + "\n"
    )
    if args.zip:
        bpy.ops.preferences.addon_disable(module="roof_generator")
    else:
        roof_generator.unregister()
    print("CANONICAL_ADDON_SMOKE_OK")


if __name__ == "__main__":
    main()
