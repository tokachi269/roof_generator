from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np


@dataclass
class RoofRay:
    oeid: tuple[int, int]
    edgetype: int
    ray_type: int
    point: tuple[float, float]
    direction: tuple[float, float]
    vid: list[int] = field(default_factory=list)
    count: int = 0


@dataclass(frozen=True)
class DualPrimalRoofGraph:
    vertices: np.ndarray
    faces: tuple[tuple[int, ...], ...]
    roofrays: tuple[RoofRay, ...]


def build_primal_roof_graph_from_dual(
    outline_vertices: np.ndarray,
    adjacency: np.ndarray,
    eps_ortho: float = 1e-6,
    eps_nndist: float = 1e-6,
) -> DualPrimalRoofGraph:
    outline_vertices = np.asarray(outline_vertices, dtype=float)
    adjacency = np.asarray(adjacency, dtype=int)
    if outline_vertices.ndim != 2 or outline_vertices.shape[1] != 2:
        raise ValueError("outline_vertices must have shape (n, 2)")
    if adjacency.ndim != 2 or adjacency.shape[0] != adjacency.shape[1]:
        raise ValueError("adjacency must be a square matrix")
    if adjacency.shape[0] != len(outline_vertices):
        raise ValueError("adjacency size must match the number of outline edges")

    dual_edges = _extract_dual_edges(adjacency)
    outline_edges = np.hstack([outline_vertices, np.roll(outline_vertices, -1, axis=0)])

    roofrays = [
        _construct_roofray_from_outline(outline_edges, edge_id1, edge_id2, outline_vertices, eps_ortho, eps_nndist)
        for edge_id1, edge_id2 in dual_edges
    ]
    vertices_ini, roof_edges = _construct_roofgraph_from_roofrays(roofrays, outline_vertices)
    faces = _extract_faces_from_roofgraph(roofrays, roof_edges, dual_edges)
    vertices = _roofgraph_laplacian_embedding(vertices_ini, roof_edges, outline_vertices)
    return DualPrimalRoofGraph(vertices=vertices, faces=faces, roofrays=tuple(roofrays))


def _extract_dual_edges(adjacency: np.ndarray) -> tuple[tuple[int, int], ...]:
    rows, cols = np.nonzero(np.triu(adjacency, k=1))
    return tuple((int(row), int(col)) for row, col in zip(rows.tolist(), cols.tolist()))


def _construct_roofray_from_outline(
    outline_edges: np.ndarray,
    edge_id1: int,
    edge_id2: int,
    outline_vertices: np.ndarray,
    eps_ortho: float,
    eps_nndist: float,
) -> RoofRay:
    edge1 = outline_edges[edge_id1]
    edge2 = outline_edges[edge_id2]

    v11 = edge1[0:2]
    v12 = edge1[2:4]
    e1 = _normalize_vector(v12 - v11)

    v21 = edge2[0:2]
    v22 = edge2[2:4]
    e2 = _normalize_vector(v22 - v21)

    if _is_parallel(e1, e2, eps_ortho):
        alignment = 1.0 if float(e1 @ e2) >= 0.0 else -1.0
        direction = e1 + alignment * e2
        if np.linalg.norm(direction) == 0.0:
            direction = e1
        direction = _normalize_vector(direction)
        return RoofRay(
            oeid=(edge_id1, edge_id2),
            edgetype=2,
            ray_type=2,
            point=tuple(((v11 + v12 + v21 + v22) / 4.0).tolist()),
            direction=tuple(direction.tolist()),
            count=2,
        )

    intersection = _find_intersection_of_two_lines(v11, e1, v21, e2, eps_ortho)
    endpoints = np.vstack([v11, v12, v21, v22])
    distances = np.linalg.norm(endpoints - intersection, axis=1)
    nearest_index = int(np.argmin(distances))
    distance_ratio = distances[nearest_index] / max(np.linalg.norm(v12 - v11), np.linalg.norm(v22 - v21))
    if distance_ratio < eps_nndist:
        point = endpoints[nearest_index]
        vertex_ids = np.flatnonzero(np.all(np.isclose(outline_vertices, point, atol=1e-12), axis=1))
        if vertex_ids.size != 1:
            raise ValueError("dual graph intersection should match exactly one outline vertex")
        return RoofRay(
            oeid=(edge_id1, edge_id2),
            edgetype=1,
            ray_type=1,
            point=tuple(point.tolist()),
            direction=(1.0, 0.0),
            vid=[int(vertex_ids[0])],
            count=1,
        )

    return RoofRay(
        oeid=(edge_id1, edge_id2),
        edgetype=2,
        ray_type=1,
        point=tuple(intersection.tolist()),
        direction=(1.0, 0.0),
        count=2,
    )


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        raise ValueError("zero-length vector is not allowed")
    return np.asarray(vector, dtype=float) / norm


def _is_parallel(edge1: np.ndarray, edge2: np.ndarray, eps_ortho: float) -> bool:
    return 1.0 - abs(float(edge1 @ edge2)) < eps_ortho


def _find_intersection_of_two_lines(
    point1: np.ndarray,
    direction1: np.ndarray,
    point2: np.ndarray,
    direction2: np.ndarray,
    eps_ortho: float,
) -> np.ndarray:
    if _is_parallel(direction1, direction2, eps_ortho):
        raise ValueError("cannot compute an intersection for parallel dual edges")

    matrix = np.array(
        [
            [direction1[0], -direction2[0]],
            [direction1[1], -direction2[1]],
        ],
        dtype=float,
    )
    values = np.asarray(point2 - point1, dtype=float)
    parameters = np.linalg.solve(matrix, values)
    intersection = point1 + parameters[0] * direction1
    residual = np.linalg.norm((point1 + parameters[0] * direction1) - (point2 + parameters[1] * direction2))
    if residual > 1e-9:
        raise ValueError("invalid line intersection in dual graph conversion")
    return intersection


def _construct_roofgraph_from_roofrays(
    roofrays: list[RoofRay],
    outline_vertices: np.ndarray,
) -> tuple[np.ndarray, tuple[tuple[int, int], ...]]:
    num_outline_vertices = len(outline_vertices)
    intersections = _detect_intersections_from_roofrays(roofrays)

    if intersections:
        random_state = np.random.default_rng(0)
        random_vertices = random_state.random((len(intersections), 2))
        vertices_ini = np.vstack([outline_vertices, random_vertices])
    else:
        vertices_ini = np.array(outline_vertices, copy=True)

    roof_edges: list[tuple[int, int]] = [(index, (index + 1) % num_outline_vertices) for index in range(num_outline_vertices)]
    for intersection_index, ray_ids in enumerate(intersections):
        new_vertex_id = num_outline_vertices + intersection_index
        for ray_id in ray_ids:
            ray = roofrays[ray_id]
            if ray.edgetype == 1:
                roof_edges.append((ray.vid[0], new_vertex_id))
                ray.vid.append(new_vertex_id)
            else:
                if not ray.vid:
                    ray.vid = [new_vertex_id]
                else:
                    roof_edges.append((ray.vid[0], new_vertex_id))
                    ray.vid.append(new_vertex_id)
    normalized_edges = sorted({_normalize_edge(edge) for edge in roof_edges})
    return vertices_ini, tuple(normalized_edges)


def _detect_intersections_from_roofrays(roofrays: list[RoofRay]) -> list[tuple[int, ...]]:
    ray_id_by_edge = {ray.oeid: index for index, ray in enumerate(roofrays)}
    ray_id_by_edge.update({(edge_id2, edge_id1): index for (edge_id1, edge_id2), index in list(ray_id_by_edge.items())})

    intersections: list[tuple[int, ...]] = []
    while True:
        check_ray_ids = [index for index, ray in enumerate(roofrays) if ray.count > 0]
        if not check_ray_ids:
            break
        search_edges = [roofrays[index].oeid for index in check_ray_ids]
        nodes: list[list[tuple[int, int]]] = [[search_edges[0]]]

        while True:
            nodes_new: list[list[tuple[int, int]]] = []
            for node in nodes:
                current_vertex = node[-1][1]
                candidate_edges = [edge for edge in search_edges if current_vertex in edge]
                for candidate_edge in candidate_edges:
                    if candidate_edge in node or (candidate_edge[1], candidate_edge[0]) in node:
                        continue
                    if candidate_edge[0] == current_vertex:
                        nodes_new.append(node + [candidate_edge])
                    else:
                        nodes_new.append(node + [(candidate_edge[1], candidate_edge[0])])

            found_intersection = False
            for node in nodes_new:
                if node[0][0] != node[-1][1]:
                    continue
                ray_ids = []
                for edge in node:
                    ray_id = ray_id_by_edge[edge]
                    roofrays[ray_id].count -= 1
                    ray_ids.append(ray_id)
                intersections.append(tuple(ray_ids))
                found_intersection = True
                break

            if found_intersection:
                break
            if not nodes_new:
                raise ValueError("failed to detect a valid roof-graph intersection from the dual graph")
            nodes = nodes_new
    return intersections


def _extract_faces_from_roofgraph(
    roofrays: Sequence[RoofRay],
    roof_edges: Sequence[tuple[int, int]],
    dual_edges: Sequence[tuple[int, int]],
) -> tuple[tuple[int, ...], ...]:
    roof_edge_set = {_normalize_edge(edge) for edge in roof_edges}
    unique_outline_edge_ids = sorted({edge_id for dual_edge in dual_edges for edge_id in dual_edge})
    faces = []
    for outline_edge_id in unique_outline_edge_ids:
        ray_ids = [ray_id for ray_id, ray in enumerate(roofrays) if outline_edge_id in ray.oeid]
        face_vertex_ids = sorted({vertex_id for ray_id in ray_ids for vertex_id in roofrays[ray_id].vid})
        if not face_vertex_ids:
            raise ValueError("dual graph produced an empty primal face")
        ordered_face = [face_vertex_ids[0]]
        remaining = set(face_vertex_ids[1:])
        while remaining:
            next_vertex_id = None
            for candidate_vertex_id in sorted(remaining):
                if _normalize_edge((ordered_face[-1], candidate_vertex_id)) in roof_edge_set:
                    next_vertex_id = candidate_vertex_id
                    break
            if next_vertex_id is None:
                raise ValueError("failed to order a reconstructed primal face from dual graph data")
            ordered_face.append(next_vertex_id)
            remaining.remove(next_vertex_id)
        faces.append(tuple(ordered_face))
    return tuple(faces)


def _roofgraph_laplacian_embedding(
    vertices_ini: np.ndarray,
    roof_edges: Sequence[tuple[int, int]],
    outline_vertices: np.ndarray,
) -> np.ndarray:
    num_outline_vertices = len(outline_vertices)
    if len(vertices_ini) == num_outline_vertices:
        return np.array(vertices_ini, copy=True)

    adjacency = np.zeros((len(vertices_ini), len(vertices_ini)), dtype=float)
    for vertex_id1, vertex_id2 in roof_edges:
        adjacency[vertex_id1, vertex_id2] = 1.0
        adjacency[vertex_id2, vertex_id1] = 1.0
    laplacian = np.diag(np.sum(adjacency, axis=1)) - adjacency

    initial_variables = vertices_ini[num_outline_vertices:, :].reshape(-1)

    def objective(values: np.ndarray) -> float:
        all_vertices = np.vstack([outline_vertices, values.reshape(-1, 2)])
        return float(np.linalg.norm(all_vertices.T @ laplacian @ all_vertices, ord="fro"))

    try:
        from scipy.optimize import minimize
    except ImportError:
        raise ImportError("paper-aligned dual-graph reconstruction requires SciPy's BFGS solver")

    result = minimize(
        objective,
        initial_variables,
        jac=lambda values: _finite_difference_gradient(objective, np.asarray(values, dtype=float)),
        method="BFGS",
        options={
            "gtol": 1e-12,
            "maxiter": 10_000,
        },
    )
    return np.vstack([outline_vertices, result.x.reshape(-1, 2)])


def _finite_difference_gradient(objective, values: np.ndarray) -> np.ndarray:
    epsilon = 1e-6
    gradient = np.zeros_like(values, dtype=float)
    for index in range(values.size):
        delta = np.zeros_like(values, dtype=float)
        delta[index] = epsilon * max(1.0, abs(values[index]))
        forward = float(objective(values + delta))
        backward = float(objective(values - delta))
        gradient[index] = (forward - backward) / (2.0 * delta[index])
    return gradient


def _normalize_edge(edge: Sequence[int]) -> tuple[int, int]:
    vertex_id1, vertex_id2 = int(edge[0]), int(edge[1])
    return (vertex_id1, vertex_id2) if vertex_id1 <= vertex_id2 else (vertex_id2, vertex_id1)
