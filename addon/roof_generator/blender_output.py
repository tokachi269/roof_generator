# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare all canonical meshes before mutating the Blender scene."""

from dataclasses import dataclass
from .core.generation import GenerationSettings
from .core.errors import UnsupportedRoofError

FEATURE_CODES = {"ridge": 1, "hip": 2, "valley": 3, "eave": 4, "gable_end": 5}


@dataclass(frozen=True)
class RoofRequest:
    source: object
    settings: GenerationSettings = GenerationSettings()
    mesh_name: str | None = None


def generate_object(
    source_object,
    *,
    roof_type="gable",
    pitch=0.5,
    eave_height=0,
    seed=0,
    mesh_name=None,
    debug_parts=False,
    hide_source=True,
):
    request = RoofRequest(
        source_object,
        GenerationSettings(roof_type, pitch, eave_height, seed),
        mesh_name,
    )
    return generate_objects(
        (request,), debug_parts=debug_parts, hide_source=hide_source
    )[0]


def generate_objects(requests, *, debug_parts=False, hide_source=True):
    import bpy

    requests = tuple(requests)
    sources = tuple(r.source for r in requests)
    if not sources or len({id(s) for s in sources}) != len(sources):
        raise UnsupportedRoofError("select distinct planar footprint objects")
    active = bpy.context.active_object
    depsgraph = bpy.context.evaluated_depsgraph_get()
    prepared = []
    for request in requests:
        try:
            result = _prepare(request, depsgraph)
        except UnsupportedRoofError as exc:
            raise UnsupportedRoofError(
                f'{request.source.name if request.source else "footprint"}: {exc}'
            ) from exc
        prepared.append((request.source, result))
    created = []
    try:
        for (source, result), request in zip(prepared, requests):
            created.append(
                (_create_mesh(source, result, request.settings, debug_parts), result)
            )
    except Exception:
        for obj, _ in created:
            data = obj.data
            materials = tuple(data.materials)
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.meshes.remove(data)
            for mat in materials:
                if mat.users == 0:
                    bpy.data.materials.remove(mat)
        raise
    if hide_source:
        for source in sources:
            source.hide_set(True)
            source.hide_render = True
    for old in bpy.context.selected_objects:
        old.select_set(False)
    for obj, _ in created:
        obj.select_set(True)
    active_index = next((i for i, s in enumerate(sources) if s == active), 0)
    bpy.context.view_layer.objects.active = created[active_index][0]
    return tuple(created)


def _prepare(request, depsgraph):
    from mathutils import Vector
    from .mesh_input import generate_footprint_mesh

    source = request.source
    if source is None or source.type != "MESH" or source.mode != "OBJECT":
        raise UnsupportedRoofError("select a filled planar footprint in Object Mode")
    evaluated = source.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        if mesh is None:
            raise UnsupportedRoofError("evaluated footprint has no mesh")
        vertices = tuple(tuple(evaluated.matrix_world @ v.co) for v in mesh.vertices)
        faces = tuple(tuple(int(i) for i in f.vertices) for f in mesh.polygons)
        transform = evaluated.matrix_world.copy()
    finally:
        evaluated.to_mesh_clear()
    linear = transform.to_3x3()
    if abs(linear.determinant()) < 1e-12:
        raise UnsupportedRoofError("source scale must be nonsingular")
    normal = linear.inverted().transposed() @ Vector((0, 0, 1))
    direction = request.settings.reference_direction
    reference = linear @ Vector((*direction, 0))
    return generate_footprint_mesh(
        vertices,
        faces,
        request.settings,
        mesh_name=request.mesh_name or f"{source.name}_roof",
        normal_hint=tuple(normal),
        reference_hint=tuple(reference),
        mesh_origin=tuple(transform.translation),
    )


def _create_mesh(source, result, settings, debug_parts):
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
        feature = data.attributes.new("roof_feature_i", "INT", "EDGE")
        for edge in data.edges:
            key = tuple(sorted(int(i) for i in edge.vertices))
            feature.data[edge.index].value = FEATURE_CODES[
                result.roof.mesh.edge_features[key]
            ]
        data.uv_layers.new(name="Roof UV")
        architecture = result.roof.generation.selected.architecture
        count = len(architecture.members) if debug_parts else 1
        colors = (
            (0.55, 0.16, 0.08, 1),
            (0.16, 0.34, 0.55, 1),
            (0.28, 0.5, 0.23, 1),
            (0.58, 0.42, 0.13, 1),
        )
        for i in range(count):
            mat = bpy.data.materials.new(f"{spec.name}_material_{i}")
            materials.append(mat)
            mat.use_nodes = True
            mat.diffuse_color = colors[i % len(colors)] if debug_parts else spec.color
            mat.node_tree.nodes["Principled BSDF"].inputs[
                "Base Color"
            ].default_value = mat.diffuse_color
            data.materials.append(mat)
        if debug_parts:
            for face, owners in zip(data.polygons, result.roof.mesh.face_cells):
                face.material_index = owners[0]
        obj = bpy.data.objects.new(spec.name, data)
        obj.location = spec.location
        obj["roof_source"] = source.name
        obj["roof_type"] = settings.roof_type
        obj["roof_pitch"] = settings.pitch
        obj["roof_seed"] = str(settings.seed)
        obj["roof_candidate_id"] = result.roof.generation.selected.id
        collection = bpy.data.collections.get("Generated roofs")
        if collection is None:
            collection = bpy.data.collections.new("Generated roofs")
            bpy.context.scene.collection.children.link(collection)
        collection.objects.link(obj)
    except Exception:
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(data)
        for mat in materials:
            if mat.users == 0:
                bpy.data.materials.remove(mat)
        raise
    return obj
