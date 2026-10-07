# SPDX-License-Identifier: GPL-3.0-or-later
"""Evaluate footprints once, validate all roofs, then create ordinary mesh objects."""

from dataclasses import dataclass
import json
from .core.roof_parts import RoofParameters
import numpy as np

FEATURE_CODES = {"ridge": 1, "hip": 2, "valley": 3, "eave": 4, "gable_end": 5}


@dataclass(frozen=True)
class RoofRequest:
    source: object
    parameters: RoofParameters = RoofParameters()
    mesh_name: str | None = None
    part_parameters: dict | None = None


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
    """Convert one footprint using the same evaluated-input batch route."""
    request = RoofRequest(
        source_object,
        RoofParameters(roof_type, pitch, eave_height),
        mesh_name,
        part_parameters,
    )
    return generate_objects(
        (request,), debug_parts=debug_parts, hide_source=hide_source
    )[0]


def generate_objects(requests, *, debug_parts=False, hide_source=True):
    """Evaluate a set of footprint/parameter requests before changing the scene."""
    import bpy
    from .core.roof_geometry import UnsupportedRoofError

    requests = tuple(requests)
    sources = tuple(request.source for request in requests)
    if not sources or len({id(source) for source in sources}) != len(sources):
        raise UnsupportedRoofError("select distinct planar footprint objects")
    active = bpy.context.active_object
    depsgraph = bpy.context.evaluated_depsgraph_get()
    prepared = []
    for request in requests:
        source = request.source
        try:
            result = _prepare(
                source,
                depsgraph,
                request.parameters,
                request.mesh_name,
                request.part_parameters,
            )
        except UnsupportedRoofError as exc:
            name = source.name if source is not None else "footprint"
            raise UnsupportedRoofError(f"{name}: {exc}") from exc
        prepared.append((source, result))
    # Unsupported input fails before any scene objects/visibility are changed.
    # Adding output meshes cannot trigger another input depsgraph evaluation.
    created = []
    try:
        for (source, result), request in zip(prepared, requests):
            created.append(
                (
                    _create_mesh(
                        source,
                        result,
                        request.parameters.roof_type,
                        request.parameters.pitch,
                        debug_parts,
                    ),
                    result,
                )
            )
    except Exception:
        for obj, _ in created:
            data = obj.data
            materials = tuple(data.materials)
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.meshes.remove(data)
            for material in materials:
                if material.users == 0:
                    bpy.data.materials.remove(material)
        raise
    if hide_source:
        for source in sources:
            source.hide_set(True)
            source.hide_render = True
    for old in bpy.context.selected_objects:
        old.select_set(False)
    for obj, _ in created:
        obj.select_set(True)
    active_index = next((i for i, source in enumerate(sources) if source == active), 0)
    bpy.context.view_layer.objects.active = created[active_index][0]
    return tuple(created)


def _prepare(source_object, depsgraph, parameters, mesh_name, part_parameters):
    from .mesh_input import generate_footprint_mesh
    from .core.roof_geometry import UnsupportedRoofError

    if source_object is None or source_object.type != "MESH":
        raise UnsupportedRoofError("select a filled planar footprint mesh")
    if source_object.mode != "OBJECT":
        raise UnsupportedRoofError("switch the footprint to Object Mode")
    # Always read the evaluated object. An evaluation error must not silently
    # substitute unmodified input geometry.
    evaluated = source_object.evaluated_get(depsgraph)
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
    return generate_footprint_mesh(
        vertices,
        faces,
        parameters,
        mesh_name=mesh_name or f"{source_object.name}_roof",
        normal_hint=tuple(hint),
        part_parameters=part_parameters,
        mesh_origin=tuple(transform[:3, 3]),
    )


def _create_mesh(source_object, result, roof_type, pitch, debug_parts):
    import bpy

    spec = result.spec
    data = bpy.data.meshes.new(spec.name)
    obj = None
    materials = []
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
            materials.append(mat)
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
        obj["roof_generator"] = "roof-graph-v1"
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
        for material in materials:
            if material.users == 0:
                bpy.data.materials.remove(material)
        raise
    return obj
