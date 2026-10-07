from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path


def _configure_script_path() -> None:
    candidates = []

    file_path = Path(__file__)
    candidates.append(file_path.parent)
    try:
        candidates.append(file_path.resolve().parent)
    except OSError:
        pass

    try:
        import bpy  # type: ignore

        current_name = file_path.name
        for text in bpy.data.texts:
            text_path = getattr(text, "filepath", "")
            if not text_path:
                continue
            path = Path(text_path)
            if path.name == current_name or current_name == "":
                candidates.append(path.parent)
    except Exception:
        pass

    for candidate in candidates:
        if not candidate:
            continue
        candidate_str = str(candidate)
        if (candidate / "blender_adapter.py").is_file() and candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
            return


_configure_script_path()


def _reload_local_modules(*module_names: str) -> None:
    for module_name in module_names:
        module = importlib.import_module(module_name)
        importlib.reload(module)


_reload_local_modules(
    "core.roof_topology",
    "core.roof_graph_io",
    "core.roof_core",
    "core.roof_pipeline",
    "core.roof_runner",
    "blender_adapter",
)

from blender_adapter import build_comparison_mesh_specs
from blender_adapter import load_roof_result_json
from blender_adapter import summarize_result


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import a roof optimization JSON result into Blender.")
    parser.add_argument("--result-json", required=True, help="Path to the JSON file produced by run_primal_roof.py")
    parser.add_argument("--mesh-name", default="roof", help="Base object name to create in Blender")
    parser.add_argument("--separation-factor", type=float, default=1.25, help="Horizontal spacing factor between initial and optimized meshes")
    parser.add_argument("--keep-scene", action="store_true", help="Do not clear the current scene before importing")
    return parser


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = build_argument_parser().parse_args(argv)

    import bpy

    payload = load_roof_result_json(args.result_json)
    mesh_specs = build_comparison_mesh_specs(payload, mesh_name=args.mesh_name, separation_factor=args.separation_factor)

    if not args.keep_scene:
        clear_scene(bpy)

    collection = ensure_collection(bpy, f"{args.mesh_name}_comparison")
    for mesh_spec in mesh_specs:
        obj = create_mesh_object(bpy, mesh_spec, collection)
        assign_material(bpy, obj, mesh_spec.color)

    print(summarize_result(payload))
    return 0


def clear_scene(bpy) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for material in list(bpy.data.materials):
        if material.users == 0:
            bpy.data.materials.remove(material)


def ensure_collection(bpy, collection_name: str):
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def create_mesh_object(bpy, mesh_spec, collection):
    mesh = bpy.data.meshes.new(mesh_spec.name)
    mesh.from_pydata(list(mesh_spec.vertices), [], [list(face) for face in mesh_spec.faces])
    mesh.update(calc_edges=True)
    write_mesh_spec_attributes(mesh, mesh_spec)

    obj = bpy.data.objects.new(mesh_spec.name, mesh)
    obj.location = mesh_spec.location
    collection.objects.link(obj)
    return obj


def write_mesh_spec_attributes(mesh, mesh_spec) -> None:
    for name, values in getattr(mesh_spec, "edge_int_attributes", {}).items():
        _write_mesh_attribute(mesh, name, "INT", "EDGE", values)
    for name, values in getattr(mesh_spec, "edge_float_attributes", {}).items():
        _write_mesh_attribute(mesh, name, "FLOAT", "EDGE", values)
    for name, values in getattr(mesh_spec, "face_int_attributes", {}).items():
        _write_mesh_attribute(mesh, name, "INT", "FACE", values)


def _write_mesh_attribute(mesh, name: str, data_type: str, domain: str, values) -> None:
    attributes = getattr(mesh, "attributes", None)
    if attributes is None:
        return

    attribute = attributes.get(name)
    if attribute is None:
        attribute = attributes.new(name=name, type=data_type, domain=domain)
    if len(attribute.data) != len(values):
        raise ValueError(f"attribute '{name}' expects {len(attribute.data)} values but received {len(values)}")
    for index, value in enumerate(values):
        attribute.data[index].value = value


def assign_material(bpy, obj, color) -> None:
    material = bpy.data.materials.new(name=f"{obj.name}_mat")
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled is not None:
        principled.inputs[0].default_value = color
        principled.inputs[7].default_value = 0.15
    if obj.data.materials:
        obj.data.materials[0] = material
    else:
        obj.data.materials.append(material)


if __name__ == "__main__":
    raise SystemExit(main())