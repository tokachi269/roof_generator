from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


FaceList = Sequence[Sequence[int]]


@dataclass(frozen=True)
class RoofEmbeddingInput:
    variable_xy_vertex_ids: tuple[int, ...]
    variable_z_vertex_ids: tuple[int, ...]
    initial_vertices: np.ndarray
    reference_vertices: np.ndarray
    faces: tuple[tuple[int, ...], ...]
    lambda_weight: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "initial_vertices", _as_vertex_array(self.initial_vertices, "initial_vertices"))
        object.__setattr__(self, "reference_vertices", _as_vertex_array(self.reference_vertices, "reference_vertices"))
        object.__setattr__(self, "variable_xy_vertex_ids", tuple(int(vertex_id) for vertex_id in self.variable_xy_vertex_ids))
        object.__setattr__(self, "variable_z_vertex_ids", tuple(int(vertex_id) for vertex_id in self.variable_z_vertex_ids))
        object.__setattr__(self, "faces", tuple(tuple(int(vertex_id) for vertex_id in face) for face in self.faces))

        if self.initial_vertices.shape != self.reference_vertices.shape:
            raise ValueError("initial_vertices and reference_vertices must have the same shape")
        if self.initial_vertices.shape[1] != 3:
            raise ValueError("vertices must have shape (n, 3)")
        _validate_vertex_ids(self.variable_xy_vertex_ids, len(self.initial_vertices), "variable_xy_vertex_ids")
        _validate_vertex_ids(self.variable_z_vertex_ids, len(self.initial_vertices), "variable_z_vertex_ids")
        _validate_faces(self.faces, len(self.initial_vertices))


def update_variable_vertex_positions(
    variables: np.ndarray,
    variable_xy_vertex_ids: Sequence[int],
    variable_z_vertex_ids: Sequence[int],
    initial_vertices: np.ndarray,
) -> np.ndarray:
    initial_vertices = _as_vertex_array(initial_vertices, "initial_vertices")
    variable_xy_vertex_ids = tuple(int(vertex_id) for vertex_id in variable_xy_vertex_ids)
    variable_z_vertex_ids = tuple(int(vertex_id) for vertex_id in variable_z_vertex_ids)

    xy_value_count = len(variable_xy_vertex_ids) * 2
    expected_size = xy_value_count + len(variable_z_vertex_ids)
    flat_variables = np.asarray(variables, dtype=float).reshape(-1)
    if flat_variables.size != expected_size:
        raise ValueError(f"variables must contain {expected_size} values, got {flat_variables.size}")

    vertices = np.array(initial_vertices, dtype=float, copy=True)
    if xy_value_count:
        vertices[np.asarray(variable_xy_vertex_ids), 0:2] = flat_variables[:xy_value_count].reshape(len(variable_xy_vertex_ids), 2)
    if variable_z_vertex_ids:
        vertices[np.asarray(variable_z_vertex_ids), 2] = flat_variables[xy_value_count:]
    return vertices


def face_planarity_energy(vertices: np.ndarray, faces: FaceList) -> float:
    vertices = _as_vertex_array(vertices, "vertices")
    _validate_faces(faces, len(vertices))

    energy = 0.0
    for face in faces:
        face_vertices = vertices[np.asarray(face)]
        covariance = np.cov(face_vertices, rowvar=False)
        smallest_eigenvalue = float(np.linalg.eigvalsh(covariance)[0])
        energy += smallest_eigenvalue
    return energy


def roof_graph_energy(variables: np.ndarray, embedding: RoofEmbeddingInput) -> float:
    vertices = update_variable_vertex_positions(
        variables,
        embedding.variable_xy_vertex_ids,
        embedding.variable_z_vertex_ids,
        embedding.initial_vertices,
    )
    planarity_energy = face_planarity_energy(vertices, embedding.faces)
    xy_regularization = float(np.linalg.norm(vertices[:, 0:2] - embedding.reference_vertices[:, 0:2], ord="fro"))
    return planarity_energy + embedding.lambda_weight * xy_regularization


def optimize_roof_planarity(embedding: RoofEmbeddingInput):
    variable_xy_indices = np.asarray(embedding.variable_xy_vertex_ids, dtype=int)
    variable_z_indices = np.asarray(embedding.variable_z_vertex_ids, dtype=int)
    initial_variables = np.concatenate(
        [
            embedding.initial_vertices[variable_xy_indices, 0:2].reshape(-1),
            embedding.initial_vertices[variable_z_indices, 2],
        ]
    )
    objective = lambda values: roof_graph_energy(values, embedding)
    gradient = lambda values: _finite_difference_gradient(objective, np.asarray(values, dtype=float))

    try:
        from scipy.optimize import minimize
    except ImportError:
        raise ImportError("paper-aligned optimization requires SciPy's BFGS solver")

    result = minimize(
        objective,
        initial_variables,
        jac=gradient,
        method="BFGS",
        options={
            "gtol": 1e-12,
            "maxiter": 10_000,
        },
    )

    optimized_vertices = update_variable_vertex_positions(
        result.x,
        embedding.variable_xy_vertex_ids,
        embedding.variable_z_vertex_ids,
        embedding.initial_vertices,
    )
    return optimized_vertices, result


def _as_vertex_array(vertices: np.ndarray, label: str) -> np.ndarray:
    array = np.asarray(vertices, dtype=float)
    if array.ndim != 2:
        raise ValueError(f"{label} must be a 2D array")
    return array


def _validate_vertex_ids(vertex_ids: Sequence[int], vertex_count: int, label: str) -> None:
    for vertex_id in vertex_ids:
        if vertex_id < 0 or vertex_id >= vertex_count:
            raise ValueError(f"{label} contains out-of-range vertex id {vertex_id}")


def _validate_faces(faces: FaceList, vertex_count: int) -> None:
    for face in faces:
        if len(face) < 3:
            raise ValueError("each face must have at least three vertices")
        for vertex_id in face:
            if vertex_id < 0 or vertex_id >= vertex_count:
                raise ValueError(f"face contains out-of-range vertex id {vertex_id}")


def _finite_difference_gradient(objective, x: np.ndarray) -> np.ndarray:
    epsilon = 1e-6
    gradient = np.zeros_like(x, dtype=float)
    for index in range(x.size):
        delta = np.zeros_like(x, dtype=float)
        delta[index] = epsilon * max(1.0, abs(x[index]))
        forward = float(objective(x + delta))
        backward = float(objective(x - delta))
        gradient[index] = (forward - backward) / (2.0 * delta[index])
    return gradient
