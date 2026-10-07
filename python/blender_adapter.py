from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Iterable

import numpy as np

from core.roof_generator import ROOF_ROLE_EAVE
from core.roof_generator import ROOF_ROLE_GABLE_END
from core.roof_generator import ROOF_ROLE_NONE
from core.roof_graph_io import read_primal_roof_graph
from core.roof_runner import solve_primal_roof_graph
from core.roof_topology_adapter import preview_generated_roof_graph
from core.roof_topology_adapter import solve_generated_roof_graph
from core.roof_topology_generator import BoundaryEdge
from core.roof_topology_generator import decompose_orthogonal_footprint_into_primitives
from core.roof_topology_generator import build_flat_roof_graph_from_primitives
from core.roof_topology_generator import build_footprint_loop
from core.roof_topology_generator import build_orthogonal_gable_roof_graph
from core.roof_topology_generator import build_single_primitive_roof_graph
from core.roof_topology_generator import classify_primitive_kind
from core.roof_topology_generator import PrimitiveKind
from core.roof_topology_generator import RoofGraph
from core.roof_topology_generator import RoofRole
from core.roof_topology_generator import UnsupportedTopologyError
from core.roof_topology_generator import generate_single_primitive_roof_graph_from_edge_roles
from core.roof_topology import build_roof_graph_topology


@dataclass(frozen=True)
class MeshSpec:
    name: str
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, ...], ...]
    location: tuple[float, float, float]
    color: tuple[float, float, float, float]
    edge_int_attributes: dict[str, tuple[int, ...]] = field(default_factory=dict)
    edge_float_attributes: dict[str, tuple[float, ...]] = field(default_factory=dict)
    face_int_attributes: dict[str, tuple[int, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class PlaneFrame:
    origin: tuple[float, float, float]
    axis_u: tuple[float, float, float]
    axis_v: tuple[float, float, float]
    axis_n: tuple[float, float, float]


SUPPORTED_INPUT_MESSAGE = (
    "Accepted input mesh shapes:\n"
    "1. A planar mesh that already encodes a primal roof graph as a 2D graph, where interior vertices are intentional roof vertices or ridges.\n"
    "2. A single rectangle or oblique quad boundary-only footprint with explicit edge-domain role input via roof_role_i, limited to the validated flat/gable/shed cases.\n"
    "3. For other boundary-only outlines, first author the roof graph explicitly via the annotation tools or .verts/.faces input; this Blender entry path does not infer broader topology automatically in paper-aligned mode.\n"
    "Non-planar inputs are not supported."
)

SUPPORTED_PREVIEW_MESSAGE = (
    "Quick preview input mesh shapes:\n"
    "1. A single rectangle or oblique quad boundary-only footprint for flat or gable preview.\n"
    "2. An orthogonal residual outline for flat preview, decomposed into rectangle primitives.\n"
    "3. An orthogonal residual outline for cell-based gable preview, including L-, T-, U-, and multi-reflex shapes.\n"
    "4. The preview path is a convenience entry for first-pass visual checks; it is separate from the strict paper-aligned path that requires explicit roof topology input."
)


def load_roof_result_json(json_path: str | Path) -> dict:
    payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
    required_keys = {
        "initial_vertices",
        "optimized_vertices",
        "faces",
        "fixed_roof_vertex_id",
        "planarity_before",
        "planarity_after",
    }
    missing_keys = sorted(required_keys.difference(payload))
    if missing_keys:
        raise ValueError(f"roof result JSON is missing keys: {', '.join(missing_keys)}")

    normalized = {
        "initial_vertices": _normalize_vertices(payload["initial_vertices"], "initial_vertices"),
        "optimized_vertices": _normalize_vertices(payload["optimized_vertices"], "optimized_vertices"),
        "faces": _normalize_faces(payload["faces"]),
        "fixed_roof_vertex_id": int(payload["fixed_roof_vertex_id"]),
        "planarity_before": float(payload["planarity_before"]),
        "planarity_after": float(payload["planarity_after"]),
        "optimizer_success": bool(payload.get("optimizer_success", False)),
        "optimizer_message": str(payload.get("optimizer_message", "")),
        "optimizer_iterations": int(payload.get("optimizer_iterations", 0)),
    }
    if len(normalized["initial_vertices"]) != len(normalized["optimized_vertices"]):
        raise ValueError("initial_vertices and optimized_vertices must have the same length")
    return normalized


def build_comparison_mesh_specs(
    result_payload: dict,
    mesh_name: str = "roof",
    separation_factor: float = 1.25,
    boundary_edge_roles: dict[tuple[int, int], int] | None = None,
    roof_height: float | None = None,
    roof_group_id: int = 0,
) -> tuple[MeshSpec, MeshSpec]:
    faces = tuple(tuple(face) for face in result_payload["faces"])
    initial_vertices = tuple(tuple(vertex) for vertex in result_payload["initial_vertices"])
    optimized_vertices = tuple(tuple(vertex) for vertex in result_payload["optimized_vertices"])
    edge_int_attributes, edge_float_attributes, face_int_attributes = build_mesh_attribute_payload(
        result_payload,
        boundary_edge_roles=boundary_edge_roles,
        roof_height=roof_height,
        roof_group_id=roof_group_id,
    )

    width = _mesh_width(initial_vertices)
    if width <= 0.0:
        width = 1.0
    offset = width * float(separation_factor)

    initial_spec = MeshSpec(
        name=f"{mesh_name}_initial",
        vertices=initial_vertices,
        faces=faces,
        location=(-offset, 0.0, 0.0),
        color=(0.85, 0.45, 0.25, 1.0),
        edge_int_attributes=edge_int_attributes,
        edge_float_attributes=edge_float_attributes,
        face_int_attributes=face_int_attributes,
    )
    optimized_spec = MeshSpec(
        name=f"{mesh_name}_optimized",
        vertices=optimized_vertices,
        faces=faces,
        location=(offset, 0.0, 0.0),
        color=(0.2, 0.6, 0.9, 1.0),
        edge_int_attributes=edge_int_attributes,
        edge_float_attributes=edge_float_attributes,
        face_int_attributes=face_int_attributes,
    )
    return initial_spec, optimized_spec


def solve_primal_graph_to_mesh_specs(
    input_base_path: str | Path,
    mesh_name: str = "roof",
    roof_height: float = 50.0,
    lambda_weight: float = 0.0,
    fixed_roof_vertex_id: int | None = None,
    separation_factor: float = 1.25,
) -> tuple[tuple[MeshSpec, MeshSpec], dict]:
    vertices_2d, faces = read_primal_roof_graph(input_base_path)
    result = solve_primal_roof_graph(
        vertices_2d,
        faces,
        roof_height=roof_height,
        lambda_weight=lambda_weight,
        fixed_roof_vertex_id=fixed_roof_vertex_id,
    )
    payload = result.to_json_dict()
    mesh_specs = build_comparison_mesh_specs(payload, mesh_name=mesh_name, separation_factor=separation_factor)
    return mesh_specs, payload


def project_planar_mesh_to_primal(
    vertices_3d: Iterable[Iterable[float]],
    faces: Iterable[Iterable[int]],
    tolerance: float = 1e-5,
) -> tuple[np.ndarray, tuple[tuple[int, ...], ...], PlaneFrame]:
    vertices = np.asarray(tuple(tuple(float(value) for value in vertex) for vertex in vertices_3d), dtype=float)
    normalized_faces = _normalize_faces(faces)
    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise ValueError("vertices_3d must have shape (n, 3)")
    if len(vertices) < 3:
        raise ValueError("planar mesh requires at least three vertices")

    origin = vertices[0]
    axis_u = None
    axis_n = None
    for index_u in range(1, len(vertices)):
        candidate_u = vertices[index_u] - origin
        if np.linalg.norm(candidate_u) <= tolerance:
            continue
        for index_v in range(index_u + 1, len(vertices)):
            candidate_v = vertices[index_v] - origin
            normal = np.cross(candidate_u, candidate_v)
            if np.linalg.norm(normal) > tolerance:
                axis_u = candidate_u / np.linalg.norm(candidate_u)
                axis_n = normal / np.linalg.norm(normal)
                break
        if axis_u is not None:
            break

    if axis_u is None or axis_n is None:
        raise ValueError("could not determine a plane basis from the input mesh")

    distances = np.abs((vertices - origin) @ axis_n)
    if np.max(distances) > tolerance:
        raise ValueError("input mesh vertices are not planar within tolerance")

    axis_v = np.cross(axis_n, axis_u)
    projected = vertices - origin
    vertices_2d = np.column_stack([projected @ axis_u, projected @ axis_v])
    frame = PlaneFrame(
        origin=tuple(origin.tolist()),
        axis_u=tuple(axis_u.tolist()),
        axis_v=tuple(axis_v.tolist()),
        axis_n=tuple(axis_n.tolist()),
    )
    return vertices_2d, normalized_faces, frame


def lift_local_vertices_to_world(vertices_local: Iterable[Iterable[float]], frame: PlaneFrame) -> tuple[tuple[float, float, float], ...]:
    vertices_local = np.asarray(tuple(tuple(float(value) for value in vertex) for vertex in vertices_local), dtype=float)
    if vertices_local.ndim != 2 or vertices_local.shape[1] != 3:
        raise ValueError("vertices_local must have shape (n, 3)")
    origin = np.asarray(frame.origin, dtype=float)
    axis_u = np.asarray(frame.axis_u, dtype=float)
    axis_v = np.asarray(frame.axis_v, dtype=float)
    axis_n = np.asarray(frame.axis_n, dtype=float)

    vertices_world = (
        origin
        + vertices_local[:, [0]] * axis_u
        + vertices_local[:, [1]] * axis_v
        + vertices_local[:, [2]] * axis_n
    )
    return tuple(tuple(vertex.tolist()) for vertex in vertices_world)


def solve_planar_mesh_to_mesh_specs(
    vertices_3d: Iterable[Iterable[float]],
    faces: Iterable[Iterable[int]],
    primal_faces: Iterable[Iterable[int]] | None = None,
    boundary_edge_roles: dict[tuple[int, int], int] | None = None,
    mesh_name: str = "roof",
    roof_height: float = 50.0,
    lambda_weight: float = 0.0,
    fixed_roof_vertex_id: int | None = None,
    separation_factor: float = 1.25,
) -> tuple[tuple[MeshSpec, MeshSpec], dict, PlaneFrame]:
    vertices_2d, normalized_faces, frame = project_planar_mesh_to_primal(vertices_3d, faces)
    vertices_2d, normalized_faces = resolve_planar_mesh_input(
        vertices_2d,
        normalized_faces,
        primal_faces=primal_faces,
        boundary_edge_roles=boundary_edge_roles,
    )
    result = solve_primal_roof_graph(
        vertices_2d,
        normalized_faces,
        roof_height=roof_height,
        lambda_weight=lambda_weight,
        fixed_roof_vertex_id=fixed_roof_vertex_id,
    )
    payload = result.to_json_dict()
    payload["initial_vertices"] = [list(vertex) for vertex in lift_local_vertices_to_world(payload["initial_vertices"], frame)]
    payload["optimized_vertices"] = [list(vertex) for vertex in lift_local_vertices_to_world(payload["optimized_vertices"], frame)]
    mesh_specs = build_comparison_mesh_specs(
        payload,
        mesh_name=mesh_name,
        separation_factor=separation_factor,
        boundary_edge_roles=boundary_edge_roles,
        roof_height=roof_height,
    )
    return mesh_specs, payload, frame


def solve_planar_mesh_with_role_preset_to_mesh_specs(
    vertices_3d: Iterable[Iterable[float]],
    faces: Iterable[Iterable[int]],
    roof_kind: str,
    mesh_name: str = "roof",
    roof_height: float = 50.0,
    lambda_weight: float = 0.0,
    fixed_roof_vertex_id: int | None = None,
    separation_factor: float = 1.25,
    gable_pair_mode: str = "shorter",
) -> tuple[tuple[MeshSpec, MeshSpec], dict, PlaneFrame]:
    vertices_2d, normalized_faces, frame = project_planar_mesh_to_primal(vertices_3d, faces)
    roof_graph = build_single_primitive_roof_graph_from_preset(
        vertices_2d,
        normalized_faces,
        roof_kind=roof_kind,
        roof_height=roof_height,
        gable_pair_mode=gable_pair_mode,
    )
    if roof_graph.roof_kind == "flat" and roof_graph.primitive_kind == PrimitiveKind.RESIDUAL:
        payload = _build_direct_flat_preview_payload(roof_graph)
    else:
        result = preview_generated_roof_graph(
            roof_graph,
            lambda_weight=lambda_weight,
            fixed_roof_vertex_id=fixed_roof_vertex_id,
        )
        payload = result.to_json_dict()
    payload["initial_vertices"] = [list(vertex) for vertex in lift_local_vertices_to_world(payload["initial_vertices"], frame)]
    payload["optimized_vertices"] = [list(vertex) for vertex in lift_local_vertices_to_world(payload["optimized_vertices"], frame)]
    mesh_specs = build_comparison_mesh_specs(
        payload,
        mesh_name=mesh_name,
        separation_factor=separation_factor,
    )
    return mesh_specs, payload, frame


def summarize_single_primitive_preview_input(
    vertices_3d: Iterable[Iterable[float]],
    faces: Iterable[Iterable[int]],
) -> str:
    vertices_2d, normalized_faces, _frame = project_planar_mesh_to_primal(vertices_3d, faces)
    normalized_mesh_faces = _normalize_faces(normalized_faces)
    topology = build_roof_graph_topology(vertices_2d, normalized_mesh_faces)
    contour_vertex_ids = topology.outline_contour
    contour_vertices = topology.vertices[np.asarray(contour_vertex_ids), :2]
    try:
        footprint, primitive_kind = _build_preview_footprint(contour_vertices)
        simplified_vertex_count = len(footprint.vertices)
    except Exception as exc:
        return (
            f"raw_outline_vertices={len(contour_vertex_ids)}, "
            f"preview_classification_error={exc}"
        )
    return (
        f"raw_outline_vertices={len(contour_vertex_ids)}, "
        f"simplified_outline_vertices={simplified_vertex_count}, "
        f"primitive_kind={primitive_kind.value}"
    )


def summarize_result(result_payload: dict) -> str:
    return (
        f"planarity_before={result_payload['planarity_before']:.6f}, "
        f"planarity_after={result_payload['planarity_after']:.6f}, "
        f"success={result_payload['optimizer_success']}"
    )


def summarize_planar_input(vertices_3d: Iterable[Iterable[float]], faces: Iterable[Iterable[int]]) -> str:
    vertices = np.asarray(tuple(tuple(float(value) for value in vertex) for vertex in vertices_3d), dtype=float)
    normalized_faces = _normalize_faces(faces)
    summary = [f"vertices={len(vertices)}", f"faces={len(normalized_faces)}"]
    try:
        vertices_2d, projected_faces, _frame = project_planar_mesh_to_primal(vertices, normalized_faces)
        topology = build_roof_graph_topology(vertices_2d, projected_faces)
        summary.append(f"outline_vertices={len(topology.outline_vertex_ids)}")
        summary.append(f"roof_vertices={len(topology.roof_vertex_ids)}")
    except Exception as exc:
        summary.append(f"projection_error={exc}")
    return ", ".join(summary)


def resolve_primal_graph_faces(
    mesh_faces: Iterable[Iterable[int]],
    primal_faces: Iterable[Iterable[int]] | None,
) -> tuple[tuple[int, ...], ...]:
    if primal_faces is None:
        return _normalize_faces(mesh_faces)
    return _normalize_faces(primal_faces)


def parse_primal_graph_faces(raw_faces) -> tuple[tuple[int, ...], ...] | None:
    if raw_faces is None:
        return None
    if isinstance(raw_faces, str):
        return _normalize_faces(json.loads(raw_faces))
    return _normalize_faces(raw_faces)


def ensure_roof_vertex_primal_graph(
    vertices_2d: np.ndarray,
    faces: Iterable[Iterable[int]],
) -> tuple[np.ndarray, tuple[tuple[int, ...], ...]]:
    normalized_faces = _normalize_faces(faces)
    topology = build_roof_graph_topology(vertices_2d, normalized_faces)
    if not topology.roof_vertex_ids:
        raise ValueError(
            "paper-aligned mode requires the planar mesh to already encode a roof graph with at least one interior roof vertex"
        )
    return topology.vertices[:, :2], topology.faces


def build_mesh_attribute_payload(
    result_payload: dict,
    boundary_edge_roles: dict[tuple[int, int], int] | None = None,
    roof_height: float | None = None,
    roof_group_id: int = 0,
) -> tuple[dict[str, tuple[int, ...]], dict[str, tuple[float, ...]], dict[str, tuple[int, ...]]]:
    if boundary_edge_roles is None:
        return {}, {}, {}

    faces = _normalize_faces(result_payload["faces"])
    vertices = np.asarray(result_payload["initial_vertices"], dtype=float)
    topology = build_roof_graph_topology(vertices, faces)
    normalized_roles = _normalize_boundary_edge_roles(boundary_edge_roles)

    edge_roles = [ROOF_ROLE_NONE] * len(topology.edges)
    edge_heights = [0.0] * len(topology.edges)
    edge_groups = [0] * len(topology.edges)
    for edge_id in topology.outline_edge_ids:
        edge = topology.edges[edge_id]
        edge_roles[edge_id] = int(normalized_roles.get(edge, ROOF_ROLE_NONE))
        edge_groups[edge_id] = int(roof_group_id)
        if roof_height is not None:
            edge_heights[edge_id] = float(roof_height)

    face_regions = [int(roof_group_id)] * len(faces)
    return (
        {
            "roof_role_i": tuple(edge_roles),
            "roof_group_i": tuple(edge_groups),
        },
        {
            "roof_height": tuple(edge_heights),
        },
        {
            "roof_region_i": tuple(face_regions),
        },
    )


def resolve_planar_mesh_input(
    vertices_2d: np.ndarray,
    mesh_faces: Iterable[Iterable[int]],
    primal_faces: Iterable[Iterable[int]] | None = None,
    boundary_edge_roles: dict[tuple[int, int], int] | None = None,
) -> tuple[np.ndarray, tuple[tuple[int, ...], ...]]:
    normalized_mesh_faces = _normalize_faces(mesh_faces)
    if primal_faces is not None:
        resolved_faces = resolve_primal_graph_faces(normalized_mesh_faces, primal_faces)
        try:
            return ensure_roof_vertex_primal_graph(vertices_2d, resolved_faces)
        except ValueError as exc:
            if boundary_edge_roles is None:
                raise
            if "already encode a roof graph" not in str(exc):
                raise
            return generate_primal_graph_from_boundary_roles(vertices_2d, normalized_mesh_faces, boundary_edge_roles)

    if boundary_edge_roles is not None:
        return generate_primal_graph_from_boundary_roles(vertices_2d, normalized_mesh_faces, boundary_edge_roles)

    resolved_faces = resolve_primal_graph_faces(normalized_mesh_faces, primal_faces)
    try:
        return ensure_roof_vertex_primal_graph(vertices_2d, resolved_faces)
    except ValueError as exc:
        if "already encode a roof graph" not in str(exc):
            raise
        raise


def generate_primal_graph_from_boundary_roles(
    vertices_2d: np.ndarray,
    mesh_faces: Iterable[Iterable[int]],
    boundary_edge_roles: dict[tuple[int, int], int],
) -> tuple[np.ndarray, tuple[tuple[int, ...], ...]]:
    normalized_mesh_faces = _normalize_faces(mesh_faces)
    topology = build_roof_graph_topology(vertices_2d, normalized_mesh_faces)

    normalized_roles = _normalize_boundary_edge_roles(boundary_edge_roles)
    contour_roles = []
    contour_vertex_ids = topology.outline_contour
    for index, vertex_id0 in enumerate(contour_vertex_ids):
        vertex_id1 = contour_vertex_ids[(index + 1) % len(contour_vertex_ids)]
        edge = tuple(sorted((vertex_id0, vertex_id1)))
        contour_roles.append(normalized_roles.get(edge, ROOF_ROLE_NONE))

    generated = generate_single_primitive_roof_graph_from_edge_roles(
        topology.vertices[np.asarray(contour_vertex_ids), :2],
        contour_roles,
        roof_height=1.0,
    )
    return generated.vertices_2d, generated.faces


def build_boundary_edge_role_preset(
    vertices_2d: np.ndarray,
    mesh_faces: Iterable[Iterable[int]],
    roof_kind: str,
    gable_pair_mode: str = "shorter",
) -> dict[tuple[int, int], int]:
    normalized_mesh_faces = _normalize_faces(mesh_faces)
    topology = build_roof_graph_topology(vertices_2d, normalized_mesh_faces)
    contour_vertex_ids = topology.outline_contour
    contour_vertices = topology.vertices[np.asarray(contour_vertex_ids), :2]
    footprint = build_footprint_loop(contour_vertices, [ROOF_ROLE_NONE] * len(contour_vertices))
    primitive_kind = classify_primitive_kind(footprint)
    if primitive_kind not in {PrimitiveKind.RECTANGLE, PrimitiveKind.OBLIQUE_QUAD}:
        raise ValueError("preview role presets support only a single rectangle or oblique quad outline")
    if len(contour_vertex_ids) != 4:
        raise ValueError("preview role presets require a four-edge outer contour")

    normalized_kind = str(roof_kind).strip().lower()
    contour_edges = [
        tuple(sorted((contour_vertex_ids[index], contour_vertex_ids[(index + 1) % len(contour_vertex_ids)])))
        for index in range(len(contour_vertex_ids))
    ]
    if normalized_kind == "flat":
        return {edge: ROOF_ROLE_NONE for edge in contour_edges}
    if normalized_kind != "gable":
        raise ValueError("preview role presets currently support only flat or gable")

    opposite_pairs = ((0, 2), (1, 3))
    pair_lengths = []
    for pair in opposite_pairs:
        length = 0.0
        for edge_index in pair:
            vertex_id0 = edge_index
            vertex_id1 = (edge_index + 1) % len(contour_vertices)
            length += float(np.linalg.norm(contour_vertices[vertex_id1] - contour_vertices[vertex_id0]))
        pair_lengths.append(length / 2.0)

    if gable_pair_mode not in {"shorter", "longer"}:
        raise ValueError("gable_pair_mode must be 'shorter' or 'longer'")
    target_pair_index = 0 if pair_lengths[0] <= pair_lengths[1] else 1
    if gable_pair_mode == "longer":
        target_pair_index = 1 - target_pair_index
    gable_edge_ids = opposite_pairs[target_pair_index]

    edge_roles = {}
    for edge_index, edge in enumerate(contour_edges):
        edge_roles[edge] = ROOF_ROLE_GABLE_END if edge_index in gable_edge_ids else ROOF_ROLE_EAVE
    return edge_roles


def build_single_primitive_roof_graph_from_preset(
    vertices_2d: np.ndarray,
    mesh_faces: Iterable[Iterable[int]],
    roof_kind: str,
    roof_height: float,
    gable_pair_mode: str = "shorter",
):
    normalized_mesh_faces = _normalize_faces(mesh_faces)
    topology = build_roof_graph_topology(vertices_2d, normalized_mesh_faces)
    contour_vertex_ids = topology.outline_contour
    contour_vertices = topology.vertices[np.asarray(contour_vertex_ids), :2]
    base_footprint, primitive_kind = _build_preview_footprint(contour_vertices)

    normalized_kind = str(roof_kind).strip().lower()
    if primitive_kind not in {PrimitiveKind.RECTANGLE, PrimitiveKind.OBLIQUE_QUAD}:
        if normalized_kind == "flat":
            primitives = decompose_orthogonal_footprint_into_primitives(base_footprint)
            return build_flat_roof_graph_from_primitives(primitives, roof_height=roof_height)
        if normalized_kind == "gable":
            try:
                return build_orthogonal_gable_roof_graph(
                    base_footprint,
                    roof_height=roof_height,
                    gable_pair_mode=gable_pair_mode,
                )
            except UnsupportedTopologyError as exc:
                raise ValueError(f"{_residual_preview_support_message(base_footprint)} (gable failed: {exc})") from exc
        raise ValueError(_residual_preview_support_message(base_footprint))

    if normalized_kind == "flat":
        role_sequence = [RoofRole.NONE] * len(base_footprint.boundary_edges)
    elif normalized_kind == "gable":
        role_sequence = _build_gable_role_sequence_for_footprint(base_footprint, gable_pair_mode=gable_pair_mode)
    else:
        raise ValueError("preview role presets currently support only flat or gable")

    role_footprint = build_footprint_loop(base_footprint.vertices, role_sequence)
    return build_single_primitive_roof_graph(role_footprint, roof_height=roof_height)


def _build_preview_footprint(contour_vertices: np.ndarray) -> tuple[object, PrimitiveKind]:
    tolerances = (1e-6, 1e-5, 1e-4, 1e-3, 1e-2)
    last_footprint = None
    last_kind = PrimitiveKind.RESIDUAL
    for tolerance in tolerances:
        footprint = build_footprint_loop(contour_vertices, [RoofRole.NONE] * len(contour_vertices), tolerance=tolerance)
        primitive_kind = classify_primitive_kind(footprint, tolerance=tolerance)
        if primitive_kind in {PrimitiveKind.RECTANGLE, PrimitiveKind.OBLIQUE_QUAD}:
            return footprint, primitive_kind
        last_footprint = footprint
        last_kind = primitive_kind

    rectangle_footprint = _build_preview_rectangle_bbox_footprint(contour_vertices)
    if rectangle_footprint is not None:
        return rectangle_footprint, PrimitiveKind.RECTANGLE
    return last_footprint, last_kind


def _residual_preview_support_message(base_footprint) -> str:
    flat_preview_hint = ""
    try:
        decompose_orthogonal_footprint_into_primitives(base_footprint)
    except UnsupportedTopologyError:
        pass
    else:
        flat_preview_hint = "; this orthogonal residual outline can be previewed with roof_kind='flat'"
    return (
        "preview role presets on a residual outline support roof_kind='flat' for orthogonal outlines "
        "and roof_kind='gable' for orthogonal outlines with terminal gable edges"
        f"{flat_preview_hint}"
    )


def _build_direct_flat_preview_payload(roof_graph: RoofGraph) -> dict:
    vertices_3d = []
    for vertex_id, (x_value, y_value) in enumerate(np.asarray(roof_graph.vertices_2d, dtype=float)):
        vertices_3d.append((float(x_value), float(y_value), float(roof_graph.z_hints.get(vertex_id, 0.0))))
    return {
        "initial_vertices": tuple(vertices_3d),
        "optimized_vertices": tuple(vertices_3d),
        "faces": tuple(tuple(face) for face in roof_graph.faces),
        "fixed_roof_vertex_id": -1,
        "planarity_before": 0.0,
        "planarity_after": 0.0,
        "optimizer_success": True,
        "optimizer_message": "preview used direct flat embedding for decomposed orthogonal outline",
        "optimizer_iterations": 0,
    }


def _build_preview_rectangle_bbox_footprint(contour_vertices: np.ndarray):
    vertices = np.asarray(contour_vertices, dtype=float)
    if vertices.ndim != 2 or vertices.shape[1] != 2:
        return None

    min_x = float(np.min(vertices[:, 0]))
    max_x = float(np.max(vertices[:, 0]))
    min_y = float(np.min(vertices[:, 1]))
    max_y = float(np.max(vertices[:, 1]))
    width = max_x - min_x
    height = max_y - min_y
    if width <= 1e-9 or height <= 1e-9:
        return None

    tolerance = max(width, height) * 1e-3
    bbox_area = width * height
    polygon_area = abs(_signed_area_2d(vertices))
    if bbox_area <= 1e-12:
        return None
    if abs(polygon_area - bbox_area) > max(bbox_area * 1e-3, 1e-6):
        return None

    for x_value, y_value in vertices:
        on_left = abs(x_value - min_x) <= tolerance
        on_right = abs(x_value - max_x) <= tolerance
        on_bottom = abs(y_value - min_y) <= tolerance
        on_top = abs(y_value - max_y) <= tolerance
        if not (on_left or on_right or on_bottom or on_top):
            return None

    rectangle_vertices = (
        (min_x, min_y),
        (max_x, min_y),
        (max_x, max_y),
        (min_x, max_y),
    )
    return build_footprint_loop(rectangle_vertices, [RoofRole.NONE] * 4, tolerance=tolerance)


def _signed_area_2d(vertices: np.ndarray) -> float:
    area = 0.0
    for index in range(len(vertices)):
        x0, y0 = vertices[index]
        x1, y1 = vertices[(index + 1) % len(vertices)]
        area += x0 * y1 - x1 * y0
    return area * 0.5


def _build_gable_role_sequence_for_footprint(footprint, gable_pair_mode: str):
    if len(footprint.boundary_edges) != 4:
        raise ValueError("preview gable presets require a four-edge simplified footprint")

    if gable_pair_mode not in {"shorter", "longer"}:
        raise ValueError("gable_pair_mode must be 'shorter' or 'longer'")

    vertices = np.asarray(footprint.vertices, dtype=float)
    opposite_pairs = ((0, 2), (1, 3))
    pair_lengths = []
    for pair in opposite_pairs:
        length = 0.0
        for edge_index in pair:
            vertex_id0 = edge_index
            vertex_id1 = (edge_index + 1) % len(vertices)
            length += float(np.linalg.norm(vertices[vertex_id1] - vertices[vertex_id0]))
        pair_lengths.append(length / 2.0)

    target_pair_index = 0 if pair_lengths[0] <= pair_lengths[1] else 1
    if gable_pair_mode == "longer":
        target_pair_index = 1 - target_pair_index
    gable_edge_ids = opposite_pairs[target_pair_index]

    role_sequence = []
    for edge_index in range(len(footprint.boundary_edges)):
        role_sequence.append(RoofRole.GABLE_END if edge_index in gable_edge_ids else RoofRole.EAVE)
    return role_sequence


def _normalize_vertices(raw_vertices: Iterable[Iterable[float]], label: str) -> tuple[tuple[float, float, float], ...]:
    vertices = []
    for index, raw_vertex in enumerate(raw_vertices):
        vertex = tuple(float(value) for value in raw_vertex)
        if len(vertex) != 3:
            raise ValueError(f"{label}[{index}] must contain 3 coordinates")
        vertices.append(vertex)
    return tuple(vertices)


def _normalize_faces(raw_faces: Iterable[Iterable[int]]) -> tuple[tuple[int, ...], ...]:
    faces = []
    for index, raw_face in enumerate(raw_faces):
        face = tuple(int(value) for value in raw_face)
        if len(face) < 3:
            raise ValueError(f"faces[{index}] must contain at least 3 vertex ids")
        faces.append(face)
    return tuple(faces)


def _normalize_boundary_edge_roles(boundary_edge_roles: dict[tuple[int, int], int]) -> dict[tuple[int, int], int]:
    normalized = {}
    for raw_edge, raw_role in boundary_edge_roles.items():
        if len(raw_edge) != 2:
            raise ValueError("boundary edge role keys must contain exactly 2 vertex ids")
        edge = tuple(sorted((int(raw_edge[0]), int(raw_edge[1]))))
        normalized[edge] = int(raw_role)
    return normalized


def _mesh_width(vertices: tuple[tuple[float, float, float], ...]) -> float:
    xy = np.asarray(vertices, dtype=float)[:, 0]
    return float(np.max(xy) - np.min(xy))
