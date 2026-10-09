# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Geometry Nodes for one-metre footprints and extruded building bases."""

import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from mathutils import Vector


GROUP_NAME = "Building Base · 1m"
INPUTS = (
    ("Width", 14, 1, 256, "Starting width in metres"),
    ("Depth", 16, 1, 256, "Starting depth in metres"),
    ("Max Cut", 5, 0, 256, "Maximum exterior cut in metres"),
    ("Step Length", 3, 1, 256, "Length of each random side step in metres"),
    ("Minimum Span", 2, 1, 256, "Protected central band; capped by starting dimensions"),
    ("Seed", 0, 0, 1000000, "Random variation"),
)


def node_group():
    for group in bpy.data.node_groups:
        if group.bl_idname == "GeometryNodeTree" and group.get("building_base_version") == 3:
            return group
    group = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")
    group.is_modifier = True
    group["building_base_version"] = 3
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Roof Base", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    for name, default, minimum, maximum, description in INPUTS:
        socket = group.interface.new_socket(name=name, in_out="INPUT", socket_type="NodeSocketInt")
        socket.default_value = default
        socket.min_value = minimum
        socket.max_value = maximum
        socket.description = description
    height = group.interface.new_socket(name="Height", in_out="INPUT", socket_type="NodeSocketFloat")
    height.default_value = 0
    height.min_value = 0
    height.max_value = 1000
    height.subtype = "DISTANCE"
    height.description = "Wall extrusion height in metres; zero retains the flat footprint"
    nodes, links = group.nodes, group.links

    def node(kind, label, x, y):
        result = nodes.new(kind)
        result.label = label
        result.location = (x, y)
        return result

    def wire(value, socket):
        if isinstance(value, (int, float)):
            socket.default_value = value
        else:
            links.new(value, socket)

    def calc(operation, a, b, label, x, y):
        result = node("ShaderNodeMath", label, x, y)
        result.operation = operation
        wire(a, result.inputs[0])
        wire(b, result.inputs[1])
        return result.outputs[0]

    source = node("NodeGroupInput", "Dimensions and variation", -1400, 400)
    inp = source.outputs
    grid = node("GeometryNodeMeshGrid", "1m cells", -700, 700)
    links.new(inp["Width"], grid.inputs["Size X"])
    links.new(inp["Depth"], grid.inputs["Size Y"])
    for i, dimension in enumerate(("Width", "Depth")):
        count = calc("ADD", inp[dimension], 1, dimension + " + 1 vertices", -1100, 700 + i * 160)
        links.new(count, grid.inputs["Vertices X" if i == 0 else "Vertices Y"])
    offset = node("ShaderNodeCombineXYZ", "Integer grid origin", -700, 1000)
    for i, dimension in enumerate(("Width", "Depth")):
        half = calc("MULTIPLY", inp[dimension], 0.5, dimension + " / 2", -1100, 1050 + i * 160)
        links.new(half, offset.inputs[i])
    transform = node("GeometryNodeTransform", "Local origin at lower corner", -400, 700)
    links.new(grid.outputs["Mesh"], transform.inputs["Geometry"])
    links.new(offset.outputs[0], transform.inputs["Translation"])
    position = node("GeometryNodeInputPosition", "Face centres", -1400, -100)
    xyz = node("ShaderNodeSeparateXYZ", "Grid coordinates", -1200, -100)
    links.new(position.outputs[0], xyz.inputs[0])
    row = calc("DIVIDE", xyz.outputs["Y"], inp["Step Length"], "Side step index", -1000, -100)
    block = calc("FLOOR", row, 0, "Whole steps", -800, -100)
    seed = calc("MULTIPLY", inp["Seed"], 4, "Independent random streams", -1000, -350)
    caps = []
    for i, dimension in enumerate(("Width", "Depth")):
        y = -650 - i * 550
        remaining = calc("SUBTRACT", inp[dimension], inp["Minimum Span"], "Keep central " + dimension, -1200, y)
        half = calc("MULTIPLY", remaining, 0.5, "Symmetric cut budget", -1000, y)
        whole = calc("FLOOR", half, 0, "Whole metres", -800, y)
        positive = calc("MAXIMUM", whole, 0, "Never remove the whole mesh", -600, y)
        caps.append(calc("MINIMUM", positive, inp["Max Cut"], "Limit cut depth", -400, y))
    cuts = []
    constant_id = node("FunctionNodeInputInt", "One cut for the whole end", -200, -1450)
    constant_id.integer = 0
    for i, side in enumerate(("Left", "Right", "Bottom", "Top")):
        y = -100 - i * 320
        random = node("FunctionNodeRandomValue", side + " exterior cut", 0, y)
        random.data_type = "INT"
        minimum, maximum = [s for s in random.inputs if s.type == "INT" and s.name in {"Min", "Max"}]
        minimum.default_value = 0
        links.new(caps[0 if i < 2 else 1], maximum)
        wire(block if i < 2 else constant_id.outputs[0], random.inputs["ID"])
        stream = calc("ADD", seed, i, side + " seed", -200, y)
        links.new(stream, random.inputs["Seed"])
        cuts.append(next(s for s in random.outputs if s.type == "INT"))
    right = calc("SUBTRACT", inp["Width"], cuts[1], "Right boundary", 250, -400)
    top = calc("SUBTRACT", inp["Depth"], cuts[3], "Top boundary", 250, -1050)
    masks = [
        calc("LESS_THAN", xyz.outputs["X"], cuts[0], "Outside left", 500, 0),
        calc("GREATER_THAN", xyz.outputs["X"], right, "Outside right", 500, -220),
        calc("LESS_THAN", xyz.outputs["Y"], cuts[2], "Outside bottom", 500, -440),
        calc("GREATER_THAN", xyz.outputs["Y"], top, "Outside top", 500, -660),
    ]
    mask = masks[0]
    for i, next_mask in enumerate(masks[1:]):
        mask = calc("MAXIMUM", mask, next_mask, "Any exterior cut", 750 + i * 200, -200 - i * 200)
    delete = node("GeometryNodeDeleteGeometry", "Remove exterior cells only", 1400, 700)
    delete.domain = "FACE"
    delete.mode = "ALL"
    links.new(transform.outputs["Geometry"], delete.inputs["Geometry"])
    links.new(mask, delete.inputs["Selection"])
    extrude = node("GeometryNodeExtrudeMesh", "Walls and top", 1650, 700)
    extrude.mode = "FACES"
    extrude.inputs["Individual"].default_value = False
    links.new(delete.outputs["Geometry"], extrude.inputs["Mesh"])
    links.new(inp["Height"], extrude.inputs["Offset Scale"])
    bottom = node("GeometryNodeFlipFaces", "Outward bottom", 1650, 400)
    links.new(delete.outputs["Geometry"], bottom.inputs["Mesh"])
    join = node("GeometryNodeJoinGeometry", "Close the bottom", 1900, 700)
    links.new(extrude.outputs["Mesh"], join.inputs["Geometry"])
    links.new(bottom.outputs["Mesh"], join.inputs["Geometry"])
    weld = node("GeometryNodeMergeByDistance", "Share bottom vertices", 2150, 700)
    height_margin = calc("MULTIPLY", inp["Height"], 0.1, "Keep top and bottom separate", 1900, 350)
    weld_distance = calc("MINIMUM", height_margin, 1e-6, "Weld bottom copies only", 2150, 350)
    links.new(weld_distance, weld.inputs["Distance"])
    links.new(join.outputs["Geometry"], weld.inputs["Geometry"])
    positive_height = calc("GREATER_THAN", inp["Height"], 0, "Positive wall height", 1900, 100)
    volume = node("GeometryNodeSwitch", "Zero height stays planar", 2400, 700)
    volume.input_type = "GEOMETRY"
    links.new(positive_height, volume.inputs["Switch"])
    links.new(delete.outputs["Geometry"], volume.inputs["False"])
    links.new(weld.outputs["Geometry"], volume.inputs["True"])
    top = node("GeometryNodeSeparateGeometry", "Planar roof input", 1900, -200)
    top.domain = "FACE"
    links.new(extrude.outputs["Mesh"], top.inputs["Geometry"])
    links.new(extrude.outputs["Top"], top.inputs["Selection"])
    roof_base = node("GeometryNodeSwitch", "Top or zero-height footprint", 2400, -200)
    roof_base.input_type = "GEOMETRY"
    links.new(positive_height, roof_base.inputs["Switch"])
    links.new(delete.outputs["Geometry"], roof_base.inputs["False"])
    links.new(top.outputs["Selection"], roof_base.inputs["True"])
    output = node("NodeGroupOutput", "Building base and roof input", 2650, 700)
    links.new(volume.outputs["Output"], output.inputs["Geometry"])
    links.new(roof_base.outputs["Output"], output.inputs["Roof Base"])
    from .base_roof import add_nodes
    add_nodes(group, source, output, volume.outputs["Output"])
    group.asset_mark()
    group.asset_data.description = "One-metre grid, wall height and optional existing-spec roof. Enable Roof Generator for live roof shape updates."
    return group


def set_inputs(modifier, **values):
    sockets = {item.name: item for item in modifier.node_group.interface.items_tree if item.item_type == "SOCKET" and item.in_out == "INPUT"}
    for name, value in values.items():
        socket = sockets[name]
        if bpy.app.version >= (5, 2, 0):
            getattr(modifier.properties.inputs, socket.identifier).value = value
            continue
        if socket.socket_type == "NodeSocketMenu":
            value = next(item[4] for item in modifier.id_properties_ui(socket.identifier).as_dict()["items"] if item[0] == value)
        elif socket.socket_type == "NodeSocketFloat":
            value = float(value)
        elif socket.socket_type == "NodeSocketBool":
            value = bool(value)
        elif socket.socket_type == "NodeSocketInt":
            value = int(value)
        modifier[socket.identifier] = value
    modifier.id_data.update_tag()


def input_values(modifier):
    values = {}
    for socket in modifier.node_group.interface.items_tree:
        if socket.item_type != "SOCKET" or socket.in_out != "INPUT":
            continue
        if bpy.app.version >= (5, 2, 0):
            value = getattr(modifier.properties.inputs, socket.identifier).value
        else:
            value = modifier[socket.identifier]
        if socket.socket_type == "NodeSocketMenu" and bpy.app.version < (5, 2, 0):
            value = next(item[0] for item in modifier.id_properties_ui(socket.identifier).as_dict()["items"] if item[4] == value)
        values[socket.name] = value
    return values


def copy_inputs(modifier, instance):
    for name, value in input_values(modifier).items():
        instance.inputs[name].default_value = value


class AddBaseMesh(bpy.types.Operator):
    bl_idname = "roof_generator.add_base_mesh"
    bl_label = "Create Base Meshes"
    bl_description = "Create independent building footprints using native Geometry Nodes (no dependency installation)"
    bl_options = {"REGISTER", "UNDO"}

    count: IntProperty(name="Count", default=16, min=1, max=10000)
    width: IntProperty(name="Width (m)", default=14, min=1, max=256)
    depth: IntProperty(name="Depth (m)", default=16, min=1, max=256)
    max_cut: IntProperty(name="Max Cut (m)", default=5, min=0, max=256)
    step_length: IntProperty(name="Step Length (m)", default=3, min=1, max=256)
    minimum_span: IntProperty(name="Minimum Span (m)", default=2, min=1, max=256)
    seed: IntProperty(name="Seed", default=0, min=0, max=990000)
    height: FloatProperty(name="Height", default=0, min=0, max=1000, subtype="DISTANCE", unit="LENGTH", description="Wall extrusion height; zero keeps a flat footprint")
    roof: BoolProperty(name="Roof", default=False, description="Generate a roof using the existing roof specification")
    roof_type: EnumProperty(name="Roof Type", items=[(x, x.title(), "") for x in ("flat", "gable", "hip", "shed")], default="gable")
    roof_pitch: FloatProperty(name="Roof Pitch", default=0.5, min=0.001, max=10)

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from . import base_roof
        group = node_group()
        collection = bpy.data.collections.new("Base Meshes")
        context.scene.collection.children.link(collection)
        for obj in context.selected_objects:
            obj.select_set(False)
        columns = math.ceil(math.sqrt(self.count))
        for index in range(self.count):
            mesh = bpy.data.meshes.new("Base")
            obj = bpy.data.objects.new(f"Base_{self.seed + index:04d}", mesh)
            collection.objects.link(obj)
            obj["building_base"] = True
            obj.location = context.scene.cursor.location + Vector(((index % columns) * (self.width + 4), (index // columns) * (self.depth + 4), 0))
            modifier = obj.modifiers.new("Building Base · 1m", "NODES")
            modifier.node_group = group
            set_inputs(modifier, **{"Width": self.width, "Depth": self.depth, "Max Cut": self.max_cut, "Step Length": self.step_length, "Minimum Span": self.minimum_span, "Seed": self.seed + index, "Height": self.height, "Roof": self.roof, "Roof Type": self.roof_type.title(), "Roof Pitch": self.roof_pitch})
            if self.roof:
                try:
                    base_roof.sync(obj)
                except (ValueError, ImportError, RuntimeError) as exc:
                    obj["building_base_error"] = str(exc)
                    self.report({"WARNING"}, "Base created; roof unavailable: " + str(exc))
            obj.select_set(True)
        context.view_layer.objects.active = obj
        self.report({"INFO"}, f"Created {self.count} base meshes; edit each Geometry Nodes modifier to vary its shape")
        return {"FINISHED"}


class RetryBaseRoof(bpy.types.Operator):
    bl_idname = "roof_generator.retry_base_roof"
    bl_label = "Retry Roof"
    bl_description = "Retry roof generation after resolving the reported error"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        from .base_roof import modifier_of
        return context.object is not None and modifier_of(context.object) is not None

    def execute(self, context):
        from . import base_roof
        base_roof.retry(context.object)
        return {"FINISHED"}


class BaseMeshPanel(bpy.types.Panel):
    bl_label = "Base Mesh"
    bl_idname = "VIEW3D_PT_building_base"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Building"

    def draw(self, context):
        self.layout.operator(AddBaseMesh.bl_idname, icon="MESH_GRID")
        self.layout.label(text="1m grid · no holes")
        self.layout.label(text="Height extrudes closed walls")
        self.layout.label(text="Edit inputs in the modifier")
        if context.object and context.object.get("building_base_error"):
            self.layout.label(text="Roof generation failed", icon="ERROR")
            self.layout.label(text=context.object["building_base_error"])
            self.layout.operator(RetryBaseRoof.bl_idname)


CLASSES = (AddBaseMesh, RetryBaseRoof, BaseMeshPanel)
