# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind native base inputs to the existing roof generator, without new roof rules."""

from collections import defaultdict
import json

import bpy
from bpy.app.handlers import persistent

KINDS = ("flat", "gable", "hip", "shed")
SHAPE_INPUTS = ("Width", "Depth", "Max Cut", "Step Length", "Minimum Span", "Seed")
KEY_INPUTS = SHAPE_INPUTS + ("Roof Type", "Roof Pitch")
_pending = set()
_attempted = {}
_busy = False


def add_nodes(group, source, output, base_geometry):
    """The cached roof is valid only for the exact current generation inputs."""
    def node(kind, label, x, y):
        n = group.nodes.new(kind)
        n.label, n.location = label, (x, y)
        return n

    flag = group.interface.new_socket(name="Roof", in_out="INPUT", socket_type="NodeSocketBool")
    flag.default_value = False
    flag.force_non_field = True
    flag.description = "Generate the existing roof specification; requires enabled Roof Generator for live shape edits"
    menu = group.interface.new_socket(name="Roof Type", in_out="INPUT", socket_type="NodeSocketMenu")
    menu.force_non_field = True
    types = node("GeometryNodeMenuSwitch", "Roof type", 2800, -650)
    types.data_type = "INT"
    types.enum_items.clear()
    for kind in KINDS:
        types.enum_items.new(kind.title())
    group.links.new(source.outputs["Roof Type"], types.inputs["Menu"])
    for i, kind in enumerate(KINDS):
        types.inputs[kind.title()].default_value = i
    menu.default_value = "Gable"
    pitch = group.interface.new_socket(name="Roof Pitch", in_out="INPUT", socket_type="NodeSocketFloat")
    pitch.default_value, pitch.min_value, pitch.max_value = 0.5, 0.001, 10
    pitch.force_non_field = True
    pitch.description = "Roof rise/run pitch"
    cache = group.interface.new_socket(name="Roof Mesh", in_out="INPUT", socket_type="NodeSocketObject")
    cache.hide_in_modifier = True
    group.interface.new_socket(name="Roof Surface", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    info = node("GeometryNodeObjectInfo", "Generated roof and envelope", 2800, 650)
    info.transform_space = "ORIGINAL"
    group.links.new(source.outputs["Roof Mesh"], info.inputs["Object"])
    valid = None
    for i, name in enumerate(KEY_INPUTS):
        attr = node("GeometryNodeInputNamedAttribute", name + " at generation", 2800, -950 - i * 250)
        attr.data_type = "FLOAT"
        attr.inputs["Name"].default_value = "base_key_" + name.lower().replace(" ", "_")
        stat = node("GeometryNodeAttributeStatistic", name + " cache key", 3050, -950 - i * 250)
        stat.data_type, stat.domain = "FLOAT", "POINT"
        group.links.new(info.outputs["Geometry"], stat.inputs["Geometry"])
        group.links.new(attr.outputs["Attribute"], stat.inputs["Attribute"])
        compare = node("FunctionNodeCompare", name + " unchanged", 3300, -950 - i * 250)
        compare.data_type, compare.operation = "FLOAT", "EQUAL"
        compare.inputs["Epsilon"].default_value = 0
        group.links.new(stat.outputs["Max"], compare.inputs["A"])
        group.links.new(types.outputs[0] if name == "Roof Type" else source.outputs[name], compare.inputs["B"])
        if valid is None:
            valid = compare.outputs[0]
        else:
            conjunction = node("FunctionNodeBooleanMath", "All roof inputs match", 3550, -950 - i * 250)
            conjunction.operation = "AND"
            group.links.new(valid, conjunction.inputs[0])
            group.links.new(compare.outputs[0], conjunction.inputs[1])
            valid = conjunction.outputs[0]
    surface_attr = node("GeometryNodeInputNamedAttribute", "Roof surface faces", 3050, 300)
    surface_attr.data_type = "BOOLEAN"
    surface_attr.inputs["Name"].default_value = "roof_surface"
    surface = node("GeometryNodeSeparateGeometry", "Roof surface only", 3300, 350)
    surface.domain = "FACE"
    group.links.new(info.outputs["Geometry"], surface.inputs["Geometry"])
    group.links.new(surface_attr.outputs["Attribute"], surface.inputs["Selection"])
    raised = node("FunctionNodeCompare", "Wall height is positive", 3300, 100)
    raised.data_type, raised.operation = "FLOAT", "GREATER_THAN"
    group.links.new(source.outputs["Height"], raised.inputs["A"])
    choose = node("GeometryNodeSwitch", "Zero height exports roof surface", 3550, 650)
    choose.input_type = "GEOMETRY"
    group.links.new(raised.outputs[0], choose.inputs["Switch"])
    group.links.new(surface.outputs["Selection"], choose.inputs["False"])
    group.links.new(info.outputs["Geometry"], choose.inputs["True"])
    mask = node("GeometryNodeInputNamedAttribute", "Upper vertices move with height", 3550, 250)
    mask.data_type = "FLOAT"
    mask.inputs["Name"].default_value = "roof_upper"
    multiply = node("ShaderNodeMath", "Apply wall height", 3800, 250)
    multiply.operation = "MULTIPLY"
    group.links.new(mask.outputs["Attribute"], multiply.inputs[0])
    group.links.new(source.outputs["Height"], multiply.inputs[1])
    offset = node("ShaderNodeCombineXYZ", "Height offset", 4050, 250)
    group.links.new(multiply.outputs[0], offset.inputs["Z"])
    moved = node("GeometryNodeSetPosition", "Building with roof", 4300, 650)
    group.links.new(choose.outputs["Output"], moved.inputs["Geometry"])
    group.links.new(offset.outputs[0], moved.inputs["Offset"])
    checked = node("GeometryNodeSwitch", "Never display a stale roof", 4550, 650)
    checked.input_type = "GEOMETRY"
    group.links.new(valid, checked.inputs["Switch"])
    group.links.new(base_geometry, checked.inputs["False"])
    group.links.new(moved.outputs["Geometry"], checked.inputs["True"])
    enabled = node("GeometryNodeSwitch", "Roof ON / OFF", 4800, 650)
    enabled.input_type = "GEOMETRY"
    group.links.new(source.outputs["Roof"], enabled.inputs["Switch"])
    group.links.new(base_geometry, enabled.inputs["False"])
    group.links.new(checked.outputs["Output"], enabled.inputs["True"])
    group.links.new(enabled.outputs["Output"], output.inputs["Geometry"])
    roof_surface = node("GeometryNodeSeparateGeometry", "Exposed roof output", 4800, 250)
    roof_surface.domain = "FACE"
    group.links.new(checked.outputs["Output"], roof_surface.inputs["Geometry"])
    group.links.new(surface_attr.outputs["Attribute"], roof_surface.inputs["Selection"])
    surface_on = node("GeometryNodeSwitch", "Roof output ON / OFF", 5050, 250)
    surface_on.input_type = "GEOMETRY"
    group.links.new(source.outputs["Roof"], surface_on.inputs["Switch"])
    group.links.new(roof_surface.outputs["Selection"], surface_on.inputs["True"])
    group.links.new(surface_on.outputs["Output"], output.inputs["Roof Surface"])
    output.location = (5300, 650)


def modifier_of(obj):
    return next((m for m in obj.modifiers if m.type == "NODES" and m.node_group and m.node_group.get("building_base_version") == 3), None)


def settings(modifier):
    from .base_mesh import input_values
    return input_values(modifier)


def key(values):
    # A cached proof must match the current model scope and candidate identity.
    return ("canonical-polygon-v2",) + tuple(values[name] for name in KEY_INPUTS)


def regenerate(obj):
    """Generation owner: sample the published planar output, call existing API."""
    from .base_mesh import copy_inputs, set_inputs
    from .mesh_input import generate_footprint_mesh
    from .core.generation import GenerationSettings
    modifier = modifier_of(obj)
    values = settings(modifier)
    wrapper = bpy.data.node_groups.new("Base roof input", "GeometryNodeTree")
    wrapper.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    instance = wrapper.nodes.new("GeometryNodeGroup")
    instance.node_tree = modifier.node_group
    copy_inputs(modifier, instance)
    instance.inputs["Roof"].default_value = False
    instance.inputs["Roof Mesh"].default_value = None
    out = wrapper.nodes.new("NodeGroupOutput")
    wrapper.links.new(instance.outputs["Roof Base"], out.inputs["Geometry"])
    mesh = bpy.data.meshes.new("Base roof input")
    sample = bpy.data.objects.new("Base roof input", mesh)
    obj.users_collection[0].objects.link(sample)
    sample.modifiers.new("Planar input", "NODES").node_group = wrapper
    evaluated = None
    try:
        evaluated = sample.evaluated_get(bpy.context.evaluated_depsgraph_get())
        planar = evaluated.to_mesh()
        result = generate_footprint_mesh([tuple(v.co) for v in planar.vertices], [tuple(p.vertices) for p in planar.polygons], GenerationSettings(values["Roof Type"].lower(), pitch=values["Roof Pitch"], seed=values["Seed"]), mesh_origin=(0, 0, values["Height"]))
    finally:
        if evaluated is not None:
            evaluated.to_mesh_clear()
        bpy.data.objects.remove(sample, do_unlink=True)
        bpy.data.meshes.remove(mesh)
        bpy.data.node_groups.remove(wrapper)
    vertices = list(result.spec.vertices)
    faces = list(result.spec.faces)
    incidence = defaultdict(list)
    for face in faces:
        for a, b in zip(face, face[1:] + face[:1]):
            incidence[tuple(sorted((a, b)))].append((a, b))
    successors = {items[0][0]: items[0][1] for items in incidence.values() if len(items) == 1}
    start = min(successors)
    loop, current = [], start
    while not loop or current != start:
        loop.append(current)
        current = successors[current]
    top_count, surface_count = len(vertices), len(faces)
    lower = {}
    for i in loop:
        lower[i] = len(vertices)
        vertices.append((vertices[i][0], vertices[i][1], 0))
    for a, b in zip(loop, loop[1:] + loop[:1]):
        faces.append((a, lower[a], lower[b], b))
    faces.append(tuple(lower[i] for i in reversed(loop)))
    data = bpy.data.meshes.new("Building roof envelope")
    data.from_pydata(vertices, [], faces)
    data.update()
    for name, values_on_roof in result.spec.face_int_attributes.items():
        attribute = data.attributes.new(name, "INT", "FACE")
        for i, item in enumerate(attribute.data):
            item.value = values_on_roof[i] if i < surface_count else -1
    from .blender_output import FEATURE_CODES
    features = data.attributes.new("roof_feature_i", "INT", "EDGE")
    for edge in data.edges:
        features.data[edge.index].value = FEATURE_CODES.get(result.roof.mesh.edge_features.get(tuple(sorted(edge.vertices))), 0)
    cache = values["Roof Mesh"]
    if cache is not None and len(cache.data.materials) == 2:
        for material in cache.data.materials:
            data.materials.append(material)
    else:
        for name, color in (("Base roof", result.spec.color), ("Base walls", (0.12, 0.48, 0.68, 1))):
            material = bpy.data.materials.new(name)
            material.diffuse_color = color
            material.use_nodes = True
            material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
            data.materials.append(material)
    for i, polygon in enumerate(data.polygons):
        polygon.material_index = 0 if i < surface_count else 1
    upper = data.attributes.new("roof_upper", "FLOAT", "POINT")
    for i, item in enumerate(upper.data):
        item.value = 1 if i < top_count else 0
    roof_faces = data.attributes.new("roof_surface", "BOOLEAN", "FACE")
    for i, item in enumerate(roof_faces.data):
        item.value = i < surface_count
    for name in KEY_INPUTS:
        attr = data.attributes.new("base_key_" + name.lower().replace(" ", "_"), "FLOAT", "POINT")
        value = KINDS.index(values[name].lower()) if name == "Roof Type" else values[name]
        for item in attr.data:
            item.value = value
    if cache is None:
        cache = bpy.data.objects.new("Building roof envelope", data)
        obj.users_collection[0].objects.link(cache)
        cache.hide_render = True
        cache.hide_set(True)
        cache["building_base_owner"] = obj
        set_inputs(modifier, **{"Roof Mesh": cache})
    else:
        old = cache.data
        cache.data = data
        if old.users == 0:
            bpy.data.meshes.remove(old)
    cache["building_base_key"] = json.dumps(key(values))
    obj.pop("building_base_error", None)
    obj.update_tag()


def sync(obj):
    modifier = modifier_of(obj)
    if modifier is None:
        return
    values = settings(modifier)
    if not values["Roof"]:
        obj.pop("building_base_error", None)
        _attempted.pop(obj, None)
        return
    signature = key(values)
    cache = values["Roof Mesh"]
    if cache is not None and cache.get("building_base_key") == json.dumps(signature):
        obj.pop("building_base_error", None)
        return
    if _attempted.get(obj) == signature:
        return
    _attempted[obj] = signature
    regenerate(obj)
    _attempted.pop(obj, None)


def flush():
    global _busy
    if _busy:
        return None
    _busy = True
    try:
        if _pending:
            obj = _pending.pop()
            try:
                sync(obj)
            except ReferenceError:
                pass
            except (ValueError, ImportError, RuntimeError) as exc:
                obj["building_base_error"] = str(exc)
                print(f"Base roof generation failed: {exc}")
    finally:
        _busy = False
    return 0.05 if _pending else None


def request(obj):
    _pending.add(obj)
    if not _busy and not bpy.app.timers.is_registered(flush):
        bpy.app.timers.register(flush, first_interval=0.05)


def retry(obj):
    _attempted.pop(obj, None)
    request(obj)


def update_groups():
    """Repair the published v3 graph in saved files through the node-link API."""
    for group in bpy.data.node_groups:
        if group.get("building_base_version") != 3:
            continue
        output = next(n for n in group.nodes if n.bl_idname == "NodeGroupOutput" and n.is_active_output)
        enabled = output.inputs["Geometry"].links[0].from_node
        checked = enabled.inputs["True"].links[0].from_node
        if not checked.inputs["False"].is_linked:
            group.links.new(enabled.inputs["False"].links[0].from_socket, checked.inputs["False"])
            group.update_tag()


@persistent
def observe(scene, depsgraph):
    if _busy:
        return
    # Observation only queues requests; generation runs in the main-thread timer.
    for update in depsgraph.updates:
        source = update.id.original
        if isinstance(source, bpy.types.Object) and modifier_of(source) is not None:
            request(source)
        elif isinstance(source, bpy.types.NodeTree) and source.get("building_base_version") == 3:
            for obj in scene.objects:
                if modifier_of(obj) is not None:
                    request(obj)


@persistent
def loaded(_):
    update_groups()
    _pending.clear()
    _attempted.clear()
    for obj in bpy.data.objects:
        if modifier_of(obj) is not None:
            request(obj)


def register():
    # Blender restricts scene data during addon registration.
    bpy.app.timers.register(initialize, first_interval=0)
    bpy.app.handlers.depsgraph_update_post.append(observe)
    bpy.app.handlers.load_post.append(loaded)


def unregister():
    if bpy.app.timers.is_registered(initialize):
        bpy.app.timers.unregister(initialize)
    if bpy.app.timers.is_registered(flush):
        bpy.app.timers.unregister(flush)
    bpy.app.handlers.depsgraph_update_post.remove(observe)
    bpy.app.handlers.load_post.remove(loaded)
    _pending.clear()
    _attempted.clear()


def initialize():
    loaded(None)
    return None
