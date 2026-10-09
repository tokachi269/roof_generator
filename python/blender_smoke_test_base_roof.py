# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual GN roof flag: primary rectangles, existing-spec differential, updates."""

from pathlib import Path
import json
import sys

import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[1]
installed = "--zip" in sys.argv
if installed:
    archive = Path(sys.argv[sys.argv.index("--zip") + 1]).resolve()
    assert bpy.ops.preferences.addon_install(filepath=str(archive), overwrite=True) == {"FINISHED"}
if installed:
    assert bpy.ops.preferences.addon_enable(module="roof_generator") == {"FINISHED"}
else:
    sys.path.insert(0, str(ROOT / "addon"))
import roof_generator
from roof_generator import base_roof
from roof_generator.base_mesh import copy_inputs, input_values, set_inputs
from roof_generator.blender_output import FEATURE_CODES
from roof_generator.core.errors import UnsupportedRoofError
from roof_generator.mesh_input import generate_footprint_mesh
from roof_generator.core.generation import GenerationSettings as RoofParameters


def output_object(obj, name):
    group = bpy.data.node_groups.new(name + " smoke", "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    node = group.nodes.new("GeometryNodeGroup")
    node.node_tree = obj.modifiers[0].node_group
    copy_inputs(obj.modifiers[0], node)
    out = group.nodes.new("NodeGroupOutput")
    group.links.new(node.outputs[name], out.inputs["Geometry"])
    sample = bpy.data.objects.new(name + " smoke", bpy.data.meshes.new(name + " smoke"))
    bpy.context.collection.objects.link(sample)
    sample.modifiers.new("Output", "NODES").node_group = group
    return sample, group, node


def mesh_copy(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return mesh.copy()
    finally:
        evaluated.to_mesh_clear()


def solid(obj, expected_volume=None):
    mesh = mesh_copy(obj)
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        assert all(e.is_manifold and e.is_contiguous for e in bm.edges), "roof/walls have unshared edges or inconsistent normals"
        assert all(v.is_manifold for v in bm.verts)
        assert len(bm.verts) - len(bm.edges) + len(bm.faces) == 2
        assert bm.calc_volume() > 0
        if expected_volume is not None:
            assert abs(bm.calc_volume() - expected_volume) < 1e-4, "analytic building volume"
        return max(v.co.z for v in bm.verts)
    finally:
        bm.free()
        bpy.data.meshes.remove(mesh)


def drain():
    while base_roof._pending:
        base_roof.flush()


def differential(obj):
    modifier = obj.modifiers[0]
    values = input_values(modifier)
    planar, group, _ = output_object(obj, "Roof Base")
    mesh = mesh_copy(planar)
    try:
        expected = generate_footprint_mesh([tuple(v.co) for v in mesh.vertices], [tuple(p.vertices) for p in mesh.polygons], RoofParameters(values["Roof Type"].lower(), pitch=values["Roof Pitch"], seed=values["Seed"]), mesh_origin=(0, 0, 0))
    finally:
        bpy.data.meshes.remove(mesh)
        data = planar.data
        bpy.data.objects.remove(planar, do_unlink=True)
        bpy.data.meshes.remove(data)
        bpy.data.node_groups.remove(group)
    surface, group, _ = output_object(obj, "Roof Surface")
    actual = mesh_copy(surface)
    try:
        def face_signature(vertices, faces):
            result = []
            for face in faces:
                coords = [tuple(round(float(x), 5) for x in vertices[i]) for i in face]
                result.append(min(tuple(coords[i:] + coords[:i]) for i in range(len(coords))))
            return sorted(result)
        actual_vertices = [tuple(v.co) for v in actual.vertices]
        assert face_signature(actual_vertices, [tuple(p.vertices) for p in actual.polygons]) == face_signature(expected.spec.vertices, expected.spec.faces), "GN roof output differs from existing generation"
        assert "roof_cell_i" in actual.attributes and "roof_feature_i" in actual.attributes
        def edge_signature(vertices, tagged):
            return sorted((tuple(sorted(tuple(round(float(x), 5) for x in vertices[i]) for i in edge)), code) for edge, code in tagged if code)
        actual_edges = [(tuple(e.vertices), actual.attributes["roof_feature_i"].data[e.index].value) for e in actual.edges]
        expected_edges = [(edge, FEATURE_CODES[kind]) for edge, kind in expected.roof.mesh.edge_features.items()]
        assert edge_signature(actual_vertices, actual_edges) == edge_signature(expected.spec.vertices, expected_edges), "ridge/hip/valley/perimeter semantics changed"
        assert sorted(a.value for a in actual.attributes["roof_cell_i"].data) == sorted(expected.spec.face_int_attributes["roof_cell_i"])
        return len(actual.polygons), len(expected.roof.mesh.faces)
    finally:
        bpy.data.meshes.remove(actual)
        data = surface.data
        bpy.data.objects.remove(surface, do_unlink=True)
        bpy.data.meshes.remove(data)
        bpy.data.node_groups.remove(group)


if not installed:
    roof_generator.register()
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
assert bpy.ops.roof_generator.add_base_mesh(count=1, width=12, depth=6, max_cut=0, height=3, roof=True) == {"FINISHED"}
obj = bpy.context.object
modifier = obj.modifiers[0]
rectangles = 0
for kind, volume, top_z, faces in (("Gable", 270, 4.5, 2), ("Hip", 261, 4.5, 4), ("Flat", 216, 3, 1), ("Shed", 324, 6, 1)):
    set_inputs(modifier, **{"Roof Type": kind})
    base_roof.sync(obj)
    assert abs(solid(obj, volume) - top_z) < 1e-6
    assert differential(obj)[0] == faces
    rectangles += 1
set_inputs(modifier, **{"Roof Type": "Gable"})
base_roof.sync(obj)
surface, group, _ = output_object(obj, "Roof Surface")
mesh = mesh_copy(surface)
assert all(abs(v.co.z - (3 + 0.5 * min(v.co.y, 6 - v.co.y))) < 1e-6 for v in mesh.vertices), "independent gable slope equation"
ridge = [e for e in mesh.edges if mesh.attributes["roof_feature_i"].data[e.index].value == FEATURE_CODES["ridge"]]
assert len(ridge) == 1
import math
assert all(math.dist(a, b) < 1e-6 for a, b in zip(sorted(tuple(mesh.vertices[i].co) for i in ridge[0].vertices), [(0, 3, 4.5), (12, 3, 4.5)]))
bpy.data.meshes.remove(mesh)
data = surface.data
bpy.data.objects.remove(surface, do_unlink=True)
bpy.data.meshes.remove(data)
bpy.data.node_groups.remove(group)
cache = input_values(modifier)["Roof Mesh"]
legacy_data = cache.data
cache["building_base_key"] = "legacy backend cache"
base_roof.sync(obj)
assert cache.data != legacy_data, "legacy cache was accepted as current roof proof"
cached_data = cache.data
set_inputs(modifier, Height=5.25)
base_roof.sync(obj)
assert cache.data == cached_data, "height edits unnecessarily rebuild roof"
assert abs(solid(obj, 432) - 6.75) < 1e-6  # 72*5.25 + 54
set_inputs(modifier, Height=0)
base_roof.sync(obj)
zero_height = mesh_copy(obj)
assert len(zero_height.polygons) == 2
bpy.data.meshes.remove(zero_height)
set_inputs(modifier, Height=3, Roof=False)
base_roof.sync(obj)
assert abs(solid(obj, 216) - 3) < 1e-6
set_inputs(modifier, Roof=True)
base_roof.sync(obj)
assert cache.data == cached_data
def base_visible_without_roof(obj):
    mesh = mesh_copy(obj)
    try:
        height = input_values(obj.modifiers[0])["Height"]
        assert mesh.polygons, "a pending or rejected roof erased the building"
        assert abs(max(v.co.z for v in mesh.vertices) - height) < 1e-6
    finally:
        bpy.data.meshes.remove(mesh)
    surface, group, _ = output_object(obj, "Roof Surface")
    mesh = mesh_copy(surface)
    try:
        assert not mesh.polygons, "a stale roof was exposed"
    finally:
        bpy.data.meshes.remove(mesh)
        data = surface.data
        bpy.data.objects.remove(surface, do_unlink=True)
        bpy.data.meshes.remove(data)
        bpy.data.node_groups.remove(group)


# Observer -> scheduled generation owner; preserve base but hide stale roof.
set_inputs(modifier, Width=14)
bpy.context.view_layer.update()
assert obj in base_roof._pending, "modifier edit did not schedule live roof update"
base_visible_without_roof(obj)
drain()
assert not obj.get("building_base_error")
differential(obj)
set_inputs(modifier, **{"Roof Pitch": 0})
base_roof.request(obj)
drain()
assert obj.get("building_base_error"), "unsupported request silently recovered"
base_visible_without_roof(obj)
set_inputs(modifier, **{"Roof Pitch": 0.5})
base_roof.request(obj)
drain()
assert not obj.get("building_base_error"), "failure did not recover after valid edit"
multi = []
unsupported = []
set_inputs(modifier, **{"Width": 14, "Depth": 16, "Max Cut": 3, "Step Length": 4, "Minimum Span": 4})
for seed in range(8):
    set_inputs(modifier, Seed=seed)
    base_roof.request(obj)
    drain()
    if obj.get("building_base_error"):
        base_visible_without_roof(obj)
        try:
            differential(obj)
        except UnsupportedRoofError as exc:
            assert str(exc) == obj["building_base_error"], "failure differs from existing generation"
            unsupported.append(seed)
        else:
            raise AssertionError("binding rejects a footprint accepted by existing generation")
    else:
        solid(obj)
        multi.append(differential(obj))
assert any(faces > 2 for faces, _ in multi), "compound roof path not exercised"
# Save an actual 16-building roof demo with explicit independent input values.
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
assert bpy.ops.roof_generator.add_base_mesh(count=16, width=14, depth=16, max_cut=3, step_length=8, minimum_span=4, height=4, roof=True) == {"FINISHED"}
buildings = [o for o in bpy.context.selected_objects if o.get("building_base")]
assert len(buildings) == 16
for building in buildings:
    solid(building)
    building.color = (0.12, 0.48, 0.68, 1)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.ops.object.camera_add(location=(104, -68, 116))
camera = bpy.context.object
from mathutils import Vector
camera.rotation_euler = (Vector((34, 38, 0)) - camera.location).to_track_quat("-Z", "Y").to_euler()
camera.data.type, camera.data.ortho_scale = "ORTHO", 110
scene = bpy.context.scene
scene.camera = camera
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_shadows = False
scene.display.shading.show_cavity = True
scene.display.shading.background_type = "WORLD"
scene.world.color = (0.04, 0.04, 0.04)
scene.render.resolution_x = scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
bpy.ops.object.select_all(action="DESELECT")
buildings[0].select_set(True)
bpy.context.view_layer.objects.active = buildings[0]
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "PROPERTIES":
            area.spaces.active.context = "MODIFIER"
        elif area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_location = (34, 38, 0)
            area.spaces.active.region_3d.view_distance = 140
            area.spaces.active.region_3d.view_rotation = camera.rotation_euler.to_quaternion()
            area.spaces.active.region_3d.view_perspective = "ORTHO"
            area.spaces.active.shading.color_type = "MATERIAL"
output = ROOT / "python/out/base_roofs"
output.mkdir(parents=True, exist_ok=True)
scene.render.filepath = "//base_roofs.png"
bpy.data.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=str(output / "base_roofs.blend"))
bpy.ops.render.render(write_still=True)
report = {"archive_sha256": __import__("hashlib").sha256(archive.read_bytes()).hexdigest() if installed else None, "analytic_rectangles": rectangles, "multi_part_differentials": multi, "unsupported_seed_differentials": unsupported, "demo_buildings": len(buildings), "flag_height_live_updates_failure": "passed"}
(output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report))
if installed:
    assert bpy.ops.preferences.addon_disable(module="roof_generator") == {"FINISHED"}
    assert base_roof.observe not in bpy.app.handlers.depsgraph_update_post
    assert bpy.ops.preferences.addon_enable(module="roof_generator") == {"FINISHED"}
    assert bpy.app.handlers.depsgraph_update_post.count(base_roof.observe) == 1
    assert bpy.ops.preferences.addon_disable(module="roof_generator") == {"FINISHED"}
else:
    roof_generator.unregister()
