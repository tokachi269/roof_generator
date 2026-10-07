from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .roof_dual import build_primal_roof_graph_from_dual
from .roof_core import face_planarity_energy
from .roof_core import optimize_roof_planarity
from .roof_pipeline import build_primal_roof_embedding


@dataclass(frozen=True)
class RoofOptimizationResult:
    initial_vertices: np.ndarray
    optimized_vertices: np.ndarray
    faces: tuple[tuple[int, ...], ...]
    fixed_roof_vertex_id: int
    planarity_before: float
    planarity_after: float
    optimizer_success: bool
    optimizer_message: str
    optimizer_iterations: int

    def to_json_dict(self) -> dict:
        return {
            "initial_vertices": self.initial_vertices.tolist(),
            "optimized_vertices": self.optimized_vertices.tolist(),
            "faces": [list(face) for face in self.faces],
            "fixed_roof_vertex_id": self.fixed_roof_vertex_id,
            "planarity_before": self.planarity_before,
            "planarity_after": self.planarity_after,
            "optimizer_success": self.optimizer_success,
            "optimizer_message": self.optimizer_message,
            "optimizer_iterations": self.optimizer_iterations,
        }


def solve_primal_roof_graph(
    vertices_2d: np.ndarray,
    faces,
    roof_height: float = 50.0,
    lambda_weight: float = 0.0,
    fixed_roof_vertex_id: int | None = None,
) -> RoofOptimizationResult:
    primal_embedding = build_primal_roof_embedding(
        vertices_2d,
        faces,
        roof_height=roof_height,
        lambda_weight=lambda_weight,
        fixed_roof_vertex_id=fixed_roof_vertex_id,
    )
    optimized_vertices, optimizer_result = optimize_roof_planarity(primal_embedding.embedding)
    planarity_before = face_planarity_energy(primal_embedding.initial_vertices, primal_embedding.topology.faces)
    planarity_after = face_planarity_energy(optimized_vertices, primal_embedding.topology.faces)
    optimizer_success = bool(optimizer_result.success) or _is_effectively_planar_solution(planarity_before, planarity_after)
    return RoofOptimizationResult(
        initial_vertices=primal_embedding.initial_vertices,
        optimized_vertices=optimized_vertices,
        faces=primal_embedding.topology.faces,
        fixed_roof_vertex_id=primal_embedding.fixed_roof_vertex_id,
        planarity_before=planarity_before,
        planarity_after=planarity_after,
        optimizer_success=optimizer_success,
        optimizer_message=str(optimizer_result.message),
        optimizer_iterations=int(getattr(optimizer_result, "nit", 0)),
    )


def solve_dual_roof_graph(
    outline_vertices: np.ndarray,
    adjacency: np.ndarray,
    roof_height: float = 50.0,
    lambda_weight: float = 0.0,
    fixed_roof_vertex_id: int | None = None,
) -> RoofOptimizationResult:
    primal_graph = build_primal_roof_graph_from_dual(outline_vertices, adjacency)
    return solve_primal_roof_graph(
        primal_graph.vertices,
        primal_graph.faces,
        roof_height=roof_height,
        lambda_weight=lambda_weight,
        fixed_roof_vertex_id=fixed_roof_vertex_id,
    )


def _is_effectively_planar_solution(planarity_before: float, planarity_after: float, tolerance: float = 1e-12) -> bool:
    return planarity_after <= planarity_before + tolerance and abs(planarity_after) <= tolerance