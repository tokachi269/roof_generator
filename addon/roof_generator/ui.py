# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender settings and conversion; topology and validation belong to core."""

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
)


class RoofSettings(bpy.types.PropertyGroup):
    roof_type: EnumProperty(
        name="Roof type",
        items=[(k, k.title(), "") for k in ("gable", "hip", "shed", "flat")],
        default="gable",
    )
    pitch: FloatProperty(name="Pitch", default=0.5, min=0.001, max=4)
    eave_height: FloatProperty(name="Eave offset", default=0)
    seed: IntProperty(name="Generation seed", default=0)
    debug_cells: BoolProperty(name="Color roof regions", default=False)
    hide_source: BoolProperty(name="Hide source footprint", default=True)


class GenerateRoof(bpy.types.Operator):
    bl_idname = "roof_generator.generate"
    bl_label = "Generate roofs"
    bl_description = "Create a validated editable roof from supported planar footprints"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and context.active_object is not None
            and context.active_object.type == "MESH"
        )

    def execute(self, context):
        from .blender_output import generate_objects, RoofRequest
        from .core.generation import GenerationSettings

        settings = context.scene.roof_generator
        try:
            sources = tuple(
                sorted(
                    (o for o in context.selected_objects if o.type == "MESH"),
                    key=lambda o: o.name,
                )
            )
            requests = tuple(
                RoofRequest(
                    o,
                    GenerationSettings(
                        settings.roof_type,
                        settings.pitch,
                        settings.eave_height,
                        settings.seed,
                    ),
                )
                for o in sources
            )
            generated = generate_objects(
                requests,
                debug_cells=settings.debug_cells,
                hide_source=settings.hide_source,
            )
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report(
            {"INFO"},
            f"{len(generated)} roofs, {sum(len(o.data.polygons) for o,_ in generated)} planar faces",
        )
        return {"FINISHED"}


class RoofPanel(bpy.types.Panel):
    bl_label = "Roof Generator"
    bl_idname = "VIEW3D_PT_roof_generator"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Roof"

    def draw(self, context):
        settings = context.scene.roof_generator
        for key in (
            "roof_type",
            "pitch",
            "eave_height",
            "seed",
            "debug_cells",
            "hide_source",
        ):
            self.layout.prop(settings, key)
        self.layout.operator("roof_generator.generate", icon="MESH_DATA")


CLASSES = (RoofSettings, GenerateRoof, RoofPanel)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.roof_generator = PointerProperty(type=RoofSettings)


def unregister():
    del bpy.types.Scene.roof_generator
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
