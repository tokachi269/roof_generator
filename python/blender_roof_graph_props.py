from __future__ import annotations

import json
from typing import Iterable

from blender_roof_solver_props import store_solver_config


def normalize_primal_graph_faces(raw_faces: Iterable[Iterable[int]]) -> tuple[tuple[int, ...], ...]:
    faces = []
    for index, raw_face in enumerate(raw_faces):
        face = tuple(int(value) for value in raw_face)
        if len(face) < 3:
            raise ValueError(f"faces[{index}] must contain at least 3 vertex ids")
        faces.append(face)
    return tuple(faces)


def decode_primal_graph_faces(raw_faces) -> tuple[tuple[int, ...], ...] | None:
    if raw_faces is None:
        return None
    if isinstance(raw_faces, str):
        return normalize_primal_graph_faces(json.loads(raw_faces))
    return normalize_primal_graph_faces(raw_faces)


def encode_primal_graph_faces(faces: Iterable[Iterable[int]]) -> str:
    normalized_faces = normalize_primal_graph_faces(faces)
    return json.dumps([list(face) for face in normalized_faces])


def extract_polygon_faces(mesh, selected_only: bool = False) -> tuple[tuple[int, ...], ...]:
    faces = []
    for polygon in mesh.polygons:
        if selected_only and not getattr(polygon, "select", False):
            continue
        faces.append(tuple(int(vertex_id) for vertex_id in polygon.vertices))
    if not faces:
        if selected_only:
            raise ValueError("no selected mesh polygons found")
        raise ValueError("source mesh must contain at least one face")
    return normalize_primal_graph_faces(faces)


def store_primal_graph_faces(target, faces: Iterable[Iterable[int]]) -> tuple[tuple[int, ...], ...]:
    normalized_faces = normalize_primal_graph_faces(faces)
    target["roof_graph_faces"] = encode_primal_graph_faces(normalized_faces)
    return normalized_faces


def clear_primal_graph_faces(target) -> bool:
    if "roof_graph_faces" in target:
        del target["roof_graph_faces"]
        return True
    return False


def store_roof_graph_metadata(target, faces: Iterable[Iterable[int]], solver_config: dict | None = None) -> tuple[tuple[int, ...], ...]:
    normalized_faces = store_primal_graph_faces(target, faces)
    if solver_config is not None:
        store_solver_config(target, solver_config)
    return normalized_faces