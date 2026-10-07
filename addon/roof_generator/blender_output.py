# SPDX-License-Identifier: GPL-3.0-or-later
"""Import validated core output; all geometry decisions precede scene changes."""

import json
import numpy as np

FEATURE_CODES = {"ridge": 1, "hip": 2, "valley": 3, "eave": 4, "gable_end": 5}


def generate_object(
    source_object,
    *,
    roof_type="gable",
    pitch=0.5,
    eave_height=0.0,
    mesh_name=None,
    debug_parts=False,
    part_parameters=None,
    hide_source=True,
):
    import bpy
    from .mesh_input import generate_footprint_mesh
    from .core.roof_parts import RoofParameters
    from .core.roof_geometry import UnsupportedRoofError

    if source_object is None or source_object.type != "MESH":
        raise UnsupportedRoofError("select a filled planar footprint mesh")
    if source_object.mode != "OBJECT":
        raise UnsupportedRoofError("switch the footprint to Object Mode")
    # Always read the evaluated object. An evaluation error must not silently
    # substitute unmodified input geometry.
    evaluated = source_object.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        if mesh is None:
            raise UnsupportedRoofError("evaluated footprint has no mesh")
        transform = np.asarray(evaluated.matrix_world, dtype=float)
        local = np.asarray([tuple(v.co) for v in mesh.vertices], dtype=float)
        vertices = local @ transform[:3, :3].T + transform[:3, 3]
        faces = tuple(tuple(int(i) for i in f.vertices) for f in mesh.polygons)
    finally:
        evaluated.to_mesh_clear()
    try:
        hint = np.linalg.inv(transform[:3, :3]).T @ [0.0, 0.0, 1.0]
    except np.linalg.LinAlgError as exc:
        raise UnsupportedRoofError("source scale must be nonsingular") from exc
    result = generate_footprint_mesh(
        vertices,
        faces,
        RoofParameters(roof_type, pitch, eave_height),
        mesh_name=mesh_name or f"{source_object.name}_roof",
        normal_hint=tuple(hint),
        part_parameters=part_parameters,
        mesh_origin=tuple(transform[:3, 3]),
    )
    spec = result.spec
    data = bpy.data.meshes.new(spec.name)
    obj = None
    try:
        data.from_pydata(spec.vertices, [], spec.faces)
        data.update()
        for name, values in spec.face_int_attributes.items():
            attribute = data.attributes.new(name, "INT", "FACE")
            for item, value in zip(attribute.data, values):
                item.value = value
        crease = data.attributes.new("roof_feature_i", "INT", "EDGE")
        for edge in data.edges:
            key = tuple(sorted(int(i) for i in edge.vertices))
            crease.data[edge.index].value = FEATURE_CODES.get(
                result.roof.mesh.edge_features.get(key), 0
            )
        data.uv_layers.new(name="Roof UV")
        parts = result.roof.topology.parts
        colors = [
            (0.55, 0.16, 0.08, 1),
            (0.16, 0.34, 0.55, 1),
            (0.28, 0.5, 0.23, 1),
            (0.58, 0.42, 0.13, 1),
        ]
        for i in range(len(parts) if debug_parts else 1):
            mat = bpy.data.materials.new(f"{spec.name}_material_{i}")
            mat.use_nodes = True
            mat.diffuse_color = colors[i % len(colors)] if debug_parts else spec.color
            mat.node_tree.nodes["Principled BSDF"].inputs[
                "Base Color"
            ].default_value = mat.diffuse_color
            data.materials.append(mat)
        if debug_parts:
            for face, owners in zip(data.polygons, result.roof.mesh.face_parts):
                face.material_index = owners[0]
        obj = bpy.data.objects.new(spec.name, data)
        obj.location = spec.location
        obj["roof_generator"] = "plane-envelope-v1"
        obj["roof_source"] = source_object.name
        obj["roof_type"] = roof_type
        obj["roof_pitch"] = pitch
        obj["roof_parts"] = json.dumps(
            [
                {
                    "id": p.id,
                    "neighbors": [n.part_id for n in p.neighbors],
                    "type": p.parameters.roof_type,
                    "sources": [list(s.original_edges) for s in p.source_edges],
                    "provenance": p.provenance,
                }
                for p in parts
            ]
        )
        obj["roof_feature_codes"] = json.dumps(FEATURE_CODES)
        collection = bpy.data.collections.get("Generated roofs")
        if collection is None:
            collection = bpy.data.collections.new("Generated roofs")
            bpy.context.scene.collection.children.link(collection)
        collection.objects.link(obj)
    except Exception:
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(data)
        raise
    if hide_source:
        source_object.hide_set(True)
        source_object.hide_render = True
    for old in bpy.context.selected_objects:
        old.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj, result
