# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender UI: explicit conversion operator, properties and dependency setup."""

from pathlib import Path
import importlib.util
import subprocess
import sys
import bpy
from .dependencies import find_host_python
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    PointerProperty,
    StringProperty,
)

PACKAGE = __package__


def dependency_available():
    directory = (
        Path(__file__).parent
        / ".roof-deps"
        / f"cp{sys.version_info.major}{sys.version_info.minor}"
    )
    if directory.is_dir() and str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    try:
        shapely = importlib.import_module("shapely")
        return hasattr(shapely, "orient_polygons") and hasattr(
            shapely, "constrained_delaunay_triangles"
        )
    except (ImportError, OSError):
        return False


class RoofSettings(bpy.types.PropertyGroup):
    roof_type: EnumProperty(
        name="Roof type",
        items=[(x, x.title(), "") for x in ("flat", "gable", "hip", "shed")],
        default="gable",
    )
    pitch: FloatProperty(name="Pitch (rise/run)", default=0.5, min=0.0, soft_max=2.0)
    eave_height: FloatProperty(name="Eave offset", default=0.0, unit="LENGTH")
    debug_parts: BoolProperty(name="Color roof parts", default=False)
    hide_source: BoolProperty(name="Hide source footprint", default=True)


class RoofPreferences(bpy.types.AddonPreferences):
    bl_idname = PACKAGE
    python_executable: StringProperty(
        name="Host Python with pip", subtype="FILE_PATH", default=""
    )

    def draw(self, context):
        layout = self.layout
        layout.label(
            text=(
                "Shapely ready"
                if dependency_available()
                else "Shapely dependency is missing"
            )
        )
        layout.prop(self, "python_executable")
        layout.operator("roof_generator.install_dependency", icon="IMPORT")
        layout.label(text="Downloads a binary wheel from PyPI using host Python.")


class InstallDependency(bpy.types.Operator):
    bl_idname = "roof_generator.install_dependency"
    bl_label = "Install Shapely (Internet)"
    bl_description = (
        "Install a wheel matching this Blender Python; needs host Python with pip"
    )

    def execute(self, context):
        entry = context.preferences.addons.get(PACKAGE)
        selected = entry.preferences.python_executable if entry else ""
        target = (
            Path(__file__).parent
            / ".roof-deps"
            / f"cp{sys.version_info.major}{sys.version_info.minor}"
        )
        try:
            host = find_host_python(
                bpy.path.abspath(selected) if selected else "",
                blender_binary=bpy.app.binary_path,
            )
            run = subprocess.run(
                [
                    host,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "--only-binary=:all:",
                    "--no-deps",
                    "--python-version",
                    f"{sys.version_info.major}.{sys.version_info.minor}",
                    "--target",
                    str(target),
                    "shapely==2.1.2",
                ],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if run.returncode:
                raise RuntimeError((run.stderr or run.stdout)[-1800:])
            importlib.invalidate_caches()
            if not dependency_available():
                raise RuntimeError("wheel installed but Shapely could not be found")
            # Import the capability-checked core rather than trusting only the filename.
            from .core import roof_geometry
        except (OSError, subprocess.SubprocessError, ImportError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, "Shapely ready; select footprints and Generate roofs")
        return {"FINISHED"}


class GenerateRoof(bpy.types.Operator):
    bl_idname = "roof_generator.generate"
    bl_label = "Generate roofs"
    bl_description = (
        "Create one validated editable roof mesh per selected planar footprint"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and context.active_object is not None
            and context.active_object.type == "MESH"
        )

    def execute(self, context):
        if not dependency_available():
            self.report({"ERROR"}, "Install Shapely from addon preferences first")
            return {"CANCELLED"}
        settings = context.scene.roof_generator
        try:
            from .blender_output import generate_objects, RoofRequest
            from .core.roof_parts import RoofParameters

            sources = tuple(
                sorted(
                    (o for o in context.selected_objects if o.type == "MESH"),
                    key=lambda o: o.name,
                )
            )
            generated = generate_objects(
                tuple(
                    RoofRequest(
                        source,
                        RoofParameters(
                            settings.roof_type, settings.pitch, settings.eave_height
                        ),
                    )
                    for source in sources
                ),
                debug_parts=settings.debug_parts,
                hide_source=settings.hide_source,
            )
        except (ValueError, ImportError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report(
            {"INFO"},
            f"{len(generated)} roofs: {sum(len(result.roof.topology.parts) for _, result in generated)} parts, "
            f"{sum(len(obj.data.polygons) for obj, _ in generated)} planar faces",
        )
        return {"FINISHED"}


class RoofPanel(bpy.types.Panel):
    bl_label = "Roof Generator"
    bl_idname = "VIEW3D_PT_roof_generator"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Roof"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.roof_generator
        for key in ("roof_type", "pitch", "eave_height", "debug_parts", "hide_source"):
            layout.prop(settings, key)
        layout.operator("roof_generator.generate", icon="MESH_DATA")
        if not dependency_available():
            layout.label(text="Install Shapely in addon preferences", icon="ERROR")
            layout.operator("roof_generator.install_dependency", icon="IMPORT")


CLASSES = (RoofSettings, RoofPreferences, InstallDependency, GenerateRoof, RoofPanel)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.roof_generator = PointerProperty(type=RoofSettings)


def unregister():
    del bpy.types.Scene.roof_generator
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
