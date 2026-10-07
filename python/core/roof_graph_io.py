from __future__ import annotations

from pathlib import Path

import numpy as np


def read_primal_roof_graph(base_path: str | Path) -> tuple[np.ndarray, tuple[tuple[int, ...], ...]]:
    base_path = Path(base_path)
    vertices_path = base_path.with_suffix(".verts")
    faces_path = base_path.with_suffix(".faces")

    vertices_2d = np.loadtxt(vertices_path, delimiter=",")
    if vertices_2d.ndim == 1:
        vertices_2d = vertices_2d.reshape(1, -1)
    if vertices_2d.shape[1] != 2:
        raise ValueError(f"expected 2D vertices in {vertices_path}, got shape {vertices_2d.shape}")

    faces: list[tuple[int, ...]] = []
    for line in faces_path.read_text(encoding="ascii").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        raw_face = np.fromstring(stripped, dtype=int, sep=",")
        sentinel = int(raw_face[0])
        matching_indices = np.flatnonzero(raw_face == sentinel)
        if matching_indices.size < 2:
            raise ValueError(f"face row must repeat its first vertex as a sentinel in {faces_path}")
        face = tuple(int(vertex_id) for vertex_id in raw_face[: matching_indices[1]])
        if len(face) < 3:
            raise ValueError(f"face must contain at least three vertices in {faces_path}")
        faces.append(face)
    return vertices_2d, tuple(faces)


def read_dual_roof_graph(base_path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    base_path = Path(base_path)
    outline_path = base_path.with_suffix(".outline")
    adjacency_path = base_path.with_suffix(".adjacency")

    outline_vertices = np.loadtxt(outline_path, delimiter=",")
    if outline_vertices.ndim == 1:
        outline_vertices = outline_vertices.reshape(1, -1)
    if outline_vertices.shape[1] != 2:
        raise ValueError(f"expected 2D outline vertices in {outline_path}, got shape {outline_vertices.shape}")

    adjacency_pairs = np.loadtxt(adjacency_path, delimiter=",", dtype=int)
    if adjacency_pairs.ndim == 1:
        adjacency_pairs = adjacency_pairs.reshape(1, -1)
    if adjacency_pairs.shape[1] != 2:
        raise ValueError(f"expected edge pairs in {adjacency_path}, got shape {adjacency_pairs.shape}")

    outline_edge_count = len(outline_vertices)
    adjacency_pairs = _normalize_dual_adjacency_pairs(adjacency_pairs, outline_edge_count, adjacency_path)
    adjacency = np.zeros((outline_edge_count, outline_edge_count), dtype=int)
    adjacency[adjacency_pairs[:, 0], adjacency_pairs[:, 1]] = 1
    adjacency[adjacency_pairs[:, 1], adjacency_pairs[:, 0]] = 1
    return outline_vertices, adjacency


def vertices_2d_to_3d(vertices_2d: np.ndarray, z_value: float = 0.0) -> np.ndarray:
    vertices_2d = np.asarray(vertices_2d, dtype=float)
    if vertices_2d.ndim != 2 or vertices_2d.shape[1] != 2:
        raise ValueError("vertices_2d must have shape (n, 2)")
    z_column = np.full((len(vertices_2d), 1), float(z_value))
    return np.hstack([vertices_2d, z_column])


def _normalize_dual_adjacency_pairs(
    adjacency_pairs: np.ndarray,
    outline_edge_count: int,
    adjacency_path: Path,
) -> np.ndarray:
    min_index = int(np.min(adjacency_pairs))
    max_index = int(np.max(adjacency_pairs))
    if 1 <= min_index and max_index <= outline_edge_count:
        return adjacency_pairs - 1
    if 0 <= min_index and max_index < outline_edge_count:
        return adjacency_pairs
    raise ValueError(
        f"adjacency pairs in {adjacency_path} must use either 0-based or 1-based outline-edge ids; "
        f"got range [{min_index}, {max_index}] for {outline_edge_count} outline edges"
    )