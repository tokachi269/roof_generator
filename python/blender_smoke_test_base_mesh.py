# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate native base meshes and save a ready-to-edit Geometry Nodes demo."""

import json
from pathlib import Path
import sys
import time

import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
installed = "--zip" in sys.argv
if installed:
    archive = Path(sys.argv[sys.argv.index("--zip") + 1]).resolve()
    assert bpy.ops.preferences.addon_install(filepath=str(archive), overwrite=True) == {"FINISHED"}
    assert bpy.ops.preferences.addon_enable(module="roof_generator") == {"FINISHED"}
else:
    sys.path.insert(0, str(ROOT / "addon"))
import roof_generator
from roof_generator.base_mesh import copy_inputs, set_inputs


def snapshot(obj, height=0):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        vertices = [tuple(v.co) for v in mesh.vertices]
        faces = [tuple(p.vertices) for p in mesh.polygons]
        assert faces, "Empty footprint"
        assert all(abs(z - height) < 1e-6 and abs(x - round(x)) < 1e-6 and abs(y - round(y)) < 1e-6 for x, y, z in vertices), "Not a planar 1m grid at the requested height"
        incidence = {}
        neighbours = {i: set() for i in range(len(faces))}
        for i, face in enumerate(faces):
            assert len(face) == 4
            assert abs(mesh.polygons[i].area - 1) < 1e-6
            assert mesh.polygons[i].normal.z > 0.99
            for a, b in zip(face, face[1:] + face[:1]):
                incidence.setdefault(tuple(sorted((a, b))), []).append(i)
        boundary = {}
        for (a, b), owners in incidence.items():
            assert len(owners) in (1, 2)
            if len(owners) == 2:
                neighbours[owners[0]].add(owners[1])
                neighbours[owners[1]].add(owners[0])
            else:
                boundary.setdefault(a, set()).add(b)
                boundary.setdefault(b, set()).add(a)
        def connected(graph):
            visited, pending = set(), [next(iter(graph))]
            while pending:
                current = pending.pop()
                if current not in visited:
                    visited.add(current)
                    pending.extend(graph[current] - visited)
            return len(visited) == len(graph)
        assert connected(neighbours), "Disconnected faces"
        assert all(len(adjacent) == 2 for adjacent in boundary.values()), "Non-manifold boundary"
        assert connected(boundary), "Hole / multiple boundary loops"
        assert len(vertices) - len(mesh.edges) + len(faces) == 1, "Not a disk"
        return vertices, faces
    finally:
        evaluated.to_mesh_clear()


def volume(obj, height, area):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        assert all(e.is_manifold and e.is_contiguous for e in bm.edges), "Open / inconsistent wall extrusion"
        assert all(v.is_manifold for v in bm.verts), "Nonmanifold solid vertex"
        assert len(bm.verts) - len(bm.edges) + len(bm.faces) == 2, "Not a closed genus-zero base"
        assert abs(bm.calc_volume() - area * height) < max(1e-6, area * height * 1e-6), "Extrusion volume differs from footprint area * height"
        assert abs(min(v.co.z for v in bm.verts)) < 1e-6
        assert abs(max(v.co.z for v in bm.verts) - height) < 1e-6
        bottom, top, walls = [], [], []
        for face in bm.faces:
            assert face.calc_area() > 0 and len(face.verts) == 4
            if face.normal.z < -0.99:
                bottom.append(face)
            elif face.normal.z > 0.99:
                top.append(face)
            else:
                walls.append(face)
        assert len(top) == len(bottom) == area and walls
        assert all(abs(face.calc_area() - 1) < 1e-6 for face in top + bottom)
        assert all(abs(face.normal.z) < 1e-6 for face in walls)
    finally:
        bm.free()
        evaluated.to_mesh_clear()


if not installed:
    roof_generator.register()
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
assert bpy.ops.roof_generator.add_base_mesh(count=16) == {"FINISHED"}
objects = sorted(bpy.context.selected_objects, key=lambda obj: obj.name)
assert len({obj.modifiers[0].node_group.as_pointer() for obj in objects}) == 1
assert "shapely" not in sys.modules
obj, modifier = objects[0], objects[0].modifiers[0]
cases = 0
for width, depth, cut, step, span in ((14, 16, 5, 3, 2), (1, 1, 256, 1, 2), (2, 19, 256, 1, 1), (31, 23, 256, 1, 2), (12, 11, 8, 256, 2), (9, 7, 0, 3, 2), (8, 8, 9, 2, 256)):
    for seed in range(32):
        set_inputs(modifier, **{"Width": width, "Depth": depth, "Max Cut": cut, "Step Length": step, "Minimum Span": span, "Seed": seed})
        bpy.context.view_layer.update()
        result = snapshot(obj)
        if cut == 0 or span >= max(width, depth):
            assert len(result[1]) == width * depth
        cases += 1
set_inputs(modifier, **{"Width": 14, "Depth": 16, "Max Cut": 5, "Step Length": 3, "Minimum Span": 2, "Seed": 0})
bpy.context.view_layer.update()
reference = snapshot(obj)
set_inputs(modifier, Seed=1)
bpy.context.view_layer.update()
assert snapshot(obj) != reference, "Seed does not change shape"
set_inputs(modifier, Seed=0)
bpy.context.view_layer.update()
assert snapshot(obj) == reference, "Non-deterministic seed"
# Exercise the public second geometry output, as a future roof node would.
wrapper = bpy.data.node_groups.new("Roof Base smoke", "GeometryNodeTree")
wrapper.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
base_node = wrapper.nodes.new("GeometryNodeGroup")
base_node.node_tree = modifier.node_group
out = wrapper.nodes.new("NodeGroupOutput")
wrapper.links.new(base_node.outputs["Roof Base"], out.inputs["Geometry"])
roof_obj = bpy.data.objects.new("Roof Base smoke", bpy.data.meshes.new("Roof Base smoke"))
bpy.context.collection.objects.link(roof_obj)
roof_obj.modifiers.new("Roof Base smoke", "NODES").node_group = wrapper
extrusion_cases = 0
for seed in range(16):
    set_inputs(modifier, Seed=seed, Height=0)
    bpy.context.view_layer.update()
    flat = snapshot(obj)
    for height in (0, 0.001, 2.75, 9.5):
        set_inputs(modifier, Height=height)
        copy_inputs(modifier, base_node)
        bpy.context.view_layer.update()
        roof = snapshot(roof_obj, height)
        assert sorted((x, y) for x, y, z in roof[0]) == sorted((x, y) for x, y, z in flat[0]), "Height changed the footprint"
        if height > 0:
            volume(obj, height, len(flat[1]))
        else:
            assert snapshot(obj) == flat
        extrusion_cases += 1
bpy.data.objects.remove(roof_obj, do_unlink=True)
bpy.data.node_groups.remove(wrapper)
set_inputs(modifier, Seed=0, Height=0)
timings = []
for seed in range(100):
    start = time.perf_counter()
    set_inputs(modifier, Seed=seed)
    bpy.context.view_layer.update()
    snapshot(obj)
    timings.append((time.perf_counter() - start) * 1000)
set_inputs(modifier, Seed=0)
for obj in objects:
    snapshot(obj)
    obj.show_wire = True
    obj.show_all_edges = True
    obj.color = (0.12, 0.48, 0.68, 1)
# The generator must remain usable as an ordinary mesh for other tools.
copy = objects[0].copy()
copy.data = objects[0].data.copy()
bpy.context.collection.objects.link(copy)
bpy.context.view_layer.objects.active = copy
bpy.ops.object.modifier_apply(modifier=copy.modifiers[0].name)
assert len(copy.data.polygons) == len(reference[1])
bpy.data.objects.remove(copy, do_unlink=True)
# Save raised buildings while retaining the 1m topology and exposed roof input.
for index, obj in enumerate(objects):
    set_inputs(obj.modifiers[0], Height=2.75 + (index % 4) * 1.5)
bpy.context.view_layer.update()
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 1
bpy.ops.object.camera_add(location=(104, -68, 116))
camera = bpy.context.object
camera.rotation_euler = (Vector((34, 38, 0)) - camera.location).to_track_quat("-Z", "Y").to_euler()
camera.data.type = "ORTHO"
camera.data.ortho_scale = 110
scene = bpy.context.scene
scene.camera = camera
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "OBJECT"
scene.display.shading.show_cavity = True
scene.display.shading.show_shadows = False
scene.display.shading.background_type = "WORLD"
scene.world.color = (0.04, 0.04, 0.04)
scene.render.resolution_x = 1000
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
bpy.ops.object.select_all(action="DESELECT")
objects[0].select_set(True)
bpy.context.view_layer.objects.active = objects[0]
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "PROPERTIES":
            area.spaces.active.context = "MODIFIER"
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_location = (34, 38, 0)
            area.spaces.active.region_3d.view_distance = 140
            area.spaces.active.region_3d.view_rotation = camera.rotation_euler.to_quaternion()
            area.spaces.active.region_3d.view_perspective = "ORTHO"
output = ROOT / "python" / "out" / "base_meshes"
output.mkdir(parents=True, exist_ok=True)
scene.render.filepath = "//base_meshes.png"
bpy.data.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=str(output / "base_meshes.blend"))
bpy.ops.render.render(write_still=True)
report = {"cases": cases, "extrusion_and_roof_base_cases": extrusion_cases, "objects": len(objects), "update_including_validation_median_ms": sorted(timings)[len(timings)//2], "update_including_validation_max_ms": max(timings)}
(output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
if installed:
    assert bpy.ops.preferences.addon_disable(module="roof_generator") == {"FINISHED"}
    assert bpy.ops.preferences.addon_enable(module="roof_generator") == {"FINISHED"}
    assert bpy.ops.preferences.addon_disable(module="roof_generator") == {"FINISHED"}
else:
    roof_generator.unregister()
