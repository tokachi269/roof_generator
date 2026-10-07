from __future__ import annotations

import numpy as np

from .roof_core import RoofEmbeddingInput
from .roof_core import face_planarity_energy
from .roof_core import optimize_roof_planarity
from .roof_graph_io import vertices_2d_to_3d
from .roof_runner import RoofOptimizationResult
from .roof_runner import solve_primal_roof_graph
from .roof_topology import build_roof_graph_topology
from .roof_topology_generator import RoofGraph
from .roof_topology_generator import PrimitiveKind
from .roof_topology_generator import UnsupportedTopologyError


def solve_generated_roof_graph(
    roof_graph: RoofGraph,
    lambda_weight: float = 0.0,
    fixed_roof_vertex_id: int | None = None,
) -> RoofOptimizationResult:
    if roof_graph.primitive_kind == PrimitiveKind.RESIDUAL and roof_graph.roof_kind != "flat":
        return _solve_constrained_generated_roof_graph(
            roof_graph,
            lambda_weight=lambda_weight,
            fixed_roof_vertex_id=fixed_roof_vertex_id,
        )

    topology = build_roof_graph_topology(roof_graph.vertices_2d, roof_graph.faces)
    if not topology.roof_vertex_ids:
        vertices_3d = vertices_2d_to_3d(roof_graph.vertices_2d, z_value=0.0)
        for vertex_id, z_value in roof_graph.z_hints.items():
            vertices_3d[vertex_id, 2] = z_value
        planarity = face_planarity_energy(vertices_3d, roof_graph.faces)
        return RoofOptimizationResult(
            initial_vertices=vertices_3d,
            optimized_vertices=np.array(vertices_3d, copy=True),
            faces=roof_graph.faces,
            fixed_roof_vertex_id=-1,
            planarity_before=planarity,
            planarity_after=planarity,
            optimizer_success=True,
            optimizer_message="roof graph requires no optimization",
            optimizer_iterations=0,
        )

    outline_z_values = [roof_graph.z_hints.get(vertex_id, 0.0) for vertex_id in topology.outline_vertex_ids]
    if any(abs(z_value) > 1e-9 for z_value in outline_z_values):
        raise UnsupportedTopologyError("current SGA21 adapter requires zero outline z hints")

    roof_z_values = [roof_graph.z_hints.get(vertex_id) for vertex_id in topology.roof_vertex_ids]
    if any(z_value is None for z_value in roof_z_values):
        raise UnsupportedTopologyError("current SGA21 adapter requires z hints for all roof vertices")
    roof_height = float(roof_z_values[0])
    if any(abs(float(z_value) - roof_height) > 1e-9 for z_value in roof_z_values[1:]):
        raise UnsupportedTopologyError("current SGA21 adapter requires uniform roof-vertex z hints")

    if fixed_roof_vertex_id is None:
        fixed_candidates = tuple(sorted(vertex_id for vertex_id in topology.roof_vertex_ids if vertex_id in roof_graph.fixed_z_vertex_ids))
        if fixed_candidates:
            fixed_roof_vertex_id = fixed_candidates[0]

    return solve_primal_roof_graph(
        roof_graph.vertices_2d,
        roof_graph.faces,
        roof_height=roof_height,
        lambda_weight=lambda_weight,
        fixed_roof_vertex_id=fixed_roof_vertex_id,
    )


def preview_generated_roof_graph(
    roof_graph: RoofGraph,
    lambda_weight: float = 0.0,
    fixed_roof_vertex_id: int | None = None,
) -> RoofOptimizationResult:
    try:
        return solve_generated_roof_graph(
            roof_graph,
            lambda_weight=lambda_weight,
            fixed_roof_vertex_id=fixed_roof_vertex_id,
        )
    except ImportError:
        preview_result = build_roof_graph_hint_result(
            roof_graph,
            optimizer_message="preview used generated z-hint embedding because SciPy is unavailable",
        )
        if abs(preview_result.planarity_after) > 1e-9:
            raise
        return preview_result


def build_roof_graph_hint_result(
    roof_graph: RoofGraph,
    optimizer_message: str,
) -> RoofOptimizationResult:
    vertices_3d = vertices_2d_to_3d(roof_graph.vertices_2d, z_value=0.0)
    for vertex_id, z_value in roof_graph.z_hints.items():
        vertices_3d[vertex_id, 2] = z_value
    planarity = face_planarity_energy(vertices_3d, roof_graph.faces)
    fixed_roof_vertex_id = -1
    topology = build_roof_graph_topology(roof_graph.vertices_2d, roof_graph.faces)
    fixed_candidates = tuple(sorted(vertex_id for vertex_id in topology.roof_vertex_ids if vertex_id in roof_graph.fixed_z_vertex_ids))
    if fixed_candidates:
        fixed_roof_vertex_id = fixed_candidates[0]
    return RoofOptimizationResult(
        initial_vertices=vertices_3d,
        optimized_vertices=np.array(vertices_3d, copy=True),
        faces=roof_graph.faces,
        fixed_roof_vertex_id=fixed_roof_vertex_id,
        planarity_before=planarity,
        planarity_after=planarity,
        optimizer_success=True,
        optimizer_message=optimizer_message,
        optimizer_iterations=0,
    )


def _solve_constrained_generated_roof_graph(
    roof_graph: RoofGraph,
    lambda_weight: float,
    fixed_roof_vertex_id: int | None,
) -> RoofOptimizationResult:
    topology = build_roof_graph_topology(roof_graph.vertices_2d, roof_graph.faces)
    missing_hint_ids = tuple(vertex_id for vertex_id in range(len(topology.vertices)) if vertex_id not in roof_graph.z_hints)
    if missing_hint_ids:
        raise UnsupportedTopologyError("generated roof graph requires z hints for every vertex")

    initial_vertices = vertices_2d_to_3d(topology.vertices, z_value=0.0)
    for vertex_id, z_value in roof_graph.z_hints.items():
        initial_vertices[vertex_id, 2] = float(z_value)

    fixed_z_vertex_ids = set(roof_graph.fixed_z_vertex_ids)
    if fixed_roof_vertex_id is not None:
        if fixed_roof_vertex_id not in topology.roof_vertex_ids:
            raise ValueError("fixed_roof_vertex_id must refer to a roof vertex")
        fixed_z_vertex_ids.add(int(fixed_roof_vertex_id))
    else:
        fixed_candidates = tuple(sorted(set(topology.roof_vertex_ids).intersection(fixed_z_vertex_ids)))
        fixed_roof_vertex_id = fixed_candidates[0] if fixed_candidates else -1

    variable_xy_vertex_ids = tuple(
        vertex_id for vertex_id in topology.roof_vertex_ids if vertex_id not in roof_graph.fixed_xy_vertex_ids
    )
    variable_z_vertex_ids = tuple(
        vertex_id for vertex_id in topology.roof_vertex_ids if vertex_id not in fixed_z_vertex_ids
    )
    planarity_before = face_planarity_energy(initial_vertices, topology.faces)
    if abs(planarity_before) <= 1e-9:
        return RoofOptimizationResult(
            initial_vertices=initial_vertices,
            optimized_vertices=np.array(initial_vertices, copy=True),
            faces=topology.faces,
            fixed_roof_vertex_id=int(fixed_roof_vertex_id),
            planarity_before=planarity_before,
            planarity_after=planarity_before,
            optimizer_success=True,
            optimizer_message="generated topology is already planar",
            optimizer_iterations=0,
        )
    if not variable_xy_vertex_ids and not variable_z_vertex_ids:
        return RoofOptimizationResult(
            initial_vertices=initial_vertices,
            optimized_vertices=np.array(initial_vertices, copy=True),
            faces=topology.faces,
            fixed_roof_vertex_id=int(fixed_roof_vertex_id),
            planarity_before=planarity_before,
            planarity_after=planarity_before,
            optimizer_success=abs(planarity_before) <= 1e-9,
            optimizer_message="generated roof graph has no free variables",
            optimizer_iterations=0,
        )

    embedding = RoofEmbeddingInput(
        variable_xy_vertex_ids=variable_xy_vertex_ids,
        variable_z_vertex_ids=variable_z_vertex_ids,
        initial_vertices=initial_vertices,
        reference_vertices=np.array(initial_vertices, copy=True),
        faces=topology.faces,
        lambda_weight=lambda_weight,
    )
    optimized_vertices, optimizer_result = optimize_roof_planarity(embedding)
    planarity_after = face_planarity_energy(optimized_vertices, topology.faces)
    optimizer_success = bool(optimizer_result.success) or (
        planarity_after <= planarity_before + 1e-12 and abs(planarity_after) <= 1e-9
    )
    return RoofOptimizationResult(
        initial_vertices=initial_vertices,
        optimized_vertices=optimized_vertices,
        faces=topology.faces,
        fixed_roof_vertex_id=int(fixed_roof_vertex_id),
        planarity_before=planarity_before,
        planarity_after=planarity_after,
        optimizer_success=optimizer_success,
        optimizer_message=str(optimizer_result.message),
        optimizer_iterations=int(getattr(optimizer_result, "nit", 0)),
    )
