from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


FaceList = Sequence[Sequence[int]]
Edge = tuple[int, int]
EPS_ORTHO = 1e-2


@dataclass(frozen=True)
class RoofGraphTopology:
    vertices: np.ndarray
    faces: tuple[tuple[int, ...], ...]
    edges: tuple[Edge, ...]
    outline_edge_ids: tuple[int, ...]
    roof_edge_ids: tuple[int, ...]
    ridge_edge_ids: tuple[int, ...]
    outline_vertex_ids: tuple[int, ...]
    roof_vertex_ids: tuple[int, ...]
    outline_contour: tuple[int, ...]

    def edge_neighboring_faces(self, edge_id: int) -> tuple[int, ...]:
        edge = self.edges[edge_id]
        neighboring_faces = []
        for face_id, face in enumerate(self.faces):
            if is_edge_in_face(edge, face):
                neighboring_faces.append(face_id)
        return tuple(neighboring_faces)

    def edge_id(self, edge: Sequence[int]) -> int:
        normalized_edge = normalize_edge(edge)
        try:
            return self.edges.index(normalized_edge)
        except ValueError:
            return 0

    def edge_direction(self, edge_id: int) -> np.ndarray:
        edge = self.vertices[np.asarray(self.edges[edge_id])]
        direction = edge[0] - edge[1]
        norm = float(np.linalg.norm(direction))
        if norm == 0.0:
            raise ValueError("edge direction is undefined for zero-length edges")
        return direction / norm

    def edge_length(self, edge_id: int) -> float:
        edge = self.vertices[np.asarray(self.edges[edge_id])]
        return float(np.linalg.norm(edge[0] - edge[1]))

    def neighboring_edge_ids(self, vertex_id: int) -> tuple[int, ...]:
        return tuple(edge_id for edge_id, edge in enumerate(self.edges) if vertex_id in edge)

    def face_outline_edge_ids(self, face_id: int) -> tuple[int, ...]:
        face_edges = face_to_edges(self.faces[face_id])
        edge_ids = [self.edges.index(edge) for edge in face_edges]
        return tuple(edge_id for edge_id in edge_ids if edge_id in self.outline_edge_ids)

    def face_ridge_edge_ids(self, face_id: int) -> tuple[int, ...]:
        face_edges = face_to_edges(self.faces[face_id])
        edge_ids = [self.edges.index(edge) for edge in face_edges]
        return tuple(edge_id for edge_id in edge_ids if edge_id in self.ridge_edge_ids)

    def face_roof_vertex_ids(self, face_id: int) -> tuple[int, ...]:
        return tuple(vertex_id for vertex_id in self.faces[face_id] if vertex_id in self.roof_vertex_ids)

    def are_faces_adjacent(self, face_id1: int, face_id2: int) -> tuple[bool, tuple[int, ...]]:
        shared_edge_ids = []
        face_edges1 = set(face_to_edges(self.faces[face_id1]))
        face_edges2 = set(face_to_edges(self.faces[face_id2]))
        for edge in face_edges1.intersection(face_edges2):
            shared_edge_ids.append(self.edges.index(edge))
        return bool(shared_edge_ids), tuple(sorted(shared_edge_ids))

    def neighboring_ridge_edge_ids(self, vertex_id: int) -> tuple[int, ...]:
        if vertex_id not in self.roof_vertex_ids:
            raise ValueError("vertex_id must refer to a roof vertex")
        return tuple(edge_id for edge_id in self.ridge_edge_ids if vertex_id in self.edges[edge_id])

    def neighboring_face_ids(self, face_id: int) -> tuple[int, ...]:
        neighboring_faces = []
        for candidate_face_id in range(len(self.faces)):
            if candidate_face_id == face_id:
                continue
            adjacent, _shared_edge_ids = self.are_faces_adjacent(face_id, candidate_face_id)
            if adjacent:
                neighboring_faces.append(candidate_face_id)
        return tuple(neighboring_faces)

    def are_edges_adjacent(self, edge_id1: int, edge_id2: int) -> tuple[bool, tuple[int, ...]]:
        shared_vertices = tuple(sorted(set(self.edges[edge_id1]).intersection(self.edges[edge_id2])))
        return bool(shared_vertices), shared_vertices

    def neighboring_outline_edge_ids(self, vertex_id: int) -> tuple[int, ...]:
        if vertex_id not in self.outline_vertex_ids:
            raise ValueError("vertex_id must refer to an outline vertex")
        return tuple(edge_id for edge_id in self.outline_edge_ids if vertex_id in self.edges[edge_id])

    def face_without_outline_edge_ids(self) -> tuple[int, ...]:
        face_ids = []
        for face_id, face in enumerate(self.faces):
            outline_edge_ids = self.face_outline_edge_ids(face_id)
            if outline_edge_ids:
                continue
            if len(face) > 3:
                face_ids.append(face_id)
                continue
            outline_vertex_count = sum(vertex_id in self.outline_vertex_ids for vertex_id in face)
            if outline_vertex_count != 1:
                face_ids.append(face_id)
        return tuple(face_ids)

    def face_with_multiple_outline_edge_ids(self) -> tuple[int, ...]:
        return tuple(face_id for face_id in range(len(self.faces)) if len(self.face_outline_edge_ids(face_id)) > 1)

    def is_graph_simple(self) -> tuple[bool, tuple[int, ...]]:
        problematic_edge_ids = []
        for edge_id in self.ridge_edge_ids:
            face_ids = self.edge_neighboring_faces(edge_id)
            if len(face_ids) != 2:
                problematic_edge_ids.append(edge_id)
                continue

            def _face_is_simple(face_id: int) -> bool:
                if self.face_outline_edge_ids(face_id):
                    return True
                return len(self.faces[face_id]) == 3

            if not (_face_is_simple(face_ids[0]) and _face_is_simple(face_ids[1])):
                problematic_edge_ids.append(edge_id)
        return not problematic_edge_ids, tuple(problematic_edge_ids)

    def neighboring_outline_vertex_ids(self, vertex_id: int) -> tuple[int, int]:
        if vertex_id not in self.outline_contour:
            raise ValueError("vertex_id must refer to an outline vertex")
        contour_index = self.outline_contour.index(vertex_id)
        previous_vertex_id = self.outline_contour[(contour_index - 1) % len(self.outline_contour)]
        next_vertex_id = self.outline_contour[(contour_index + 1) % len(self.outline_contour)]
        return previous_vertex_id, next_vertex_id

    def neighboring_face_ids_of_vertex(self, vertex_id: int) -> tuple[int, ...]:
        face_ids = []
        for edge_id in self.neighboring_edge_ids(vertex_id):
            face_ids.extend(self.edge_neighboring_faces(edge_id))
        return tuple(sorted(set(face_ids)))

    def neighboring_vertex_ids(self, vertex_id: int) -> tuple[int, ...]:
        neighboring_vertices = []
        for edge_id in self.neighboring_edge_ids(vertex_id):
            neighboring_vertices.extend(self.edges[edge_id])
        return tuple(sorted(vertex_id2 for vertex_id2 in set(neighboring_vertices) if vertex_id2 != vertex_id))

    def edge_edit_type(self, edge_id: int) -> int:
        if edge_id in self.outline_edge_ids:
            return 0
        if edge_id in self.roof_edge_ids:
            return 3

        face_ids = self.edge_neighboring_faces(edge_id)
        if len(face_ids) != 2:
            raise ValueError("ridge edge must be adjacent to exactly two faces")

        outline_edge_ids1 = self.face_outline_edge_ids(face_ids[0])
        outline_edge_ids2 = self.face_outline_edge_ids(face_ids[1])
        if not outline_edge_ids1 or not outline_edge_ids2:
            raise ValueError("ridge edge edit type requires outline edges on both neighboring faces")

        direction1 = self.edge_direction(outline_edge_ids1[0])
        direction2 = self.edge_direction(outline_edge_ids2[0])
        if 1.0 - abs(float(direction1 @ direction2)) < EPS_ORTHO:
            return 1
        return 2


def build_roof_graph_topology(
    vertices: np.ndarray,
    faces: FaceList,
    outline_edges: Sequence[Sequence[int]] | None = None,
) -> RoofGraphTopology:
    vertices = np.asarray(vertices, dtype=float)
    if vertices.ndim != 2:
        raise ValueError("vertices must be a 2D array")
    normalized_faces = tuple(tuple(int(vertex_id) for vertex_id in face) for face in faces)

    edges = extract_edges_from_faces(normalized_faces)
    vertices, edges, normalized_faces = remove_unreferenced_vertices(vertices, edges, normalized_faces)

    if outline_edges is None:
        outline_edge_ids = tuple(
            edge_id
            for edge_id, _edge in enumerate(edges)
            if len(find_edge_neighboring_faces(edges[edge_id], normalized_faces)) == 1
        )
    else:
        normalized_outline_edges = tuple(normalize_edge(edge) for edge in outline_edges)
        edge_to_id = {edge: edge_id for edge_id, edge in enumerate(edges)}
        outline_edge_ids = []
        for edge in normalized_outline_edges:
            if edge not in edge_to_id:
                raise ValueError("specified outline edge is not included in the roof graph")
            outline_edge_ids.append(edge_to_id[edge])
        outline_edge_ids = tuple(outline_edge_ids)

    outline_vertex_ids = tuple(sorted({vertex_id for edge_id in outline_edge_ids for vertex_id in edges[edge_id]}))
    roof_vertex_ids = tuple(vertex_id for vertex_id in range(len(vertices)) if vertex_id not in outline_vertex_ids)
    ridge_edge_ids = tuple(
        edge_id
        for edge_id, edge in enumerate(edges)
        if edge[0] in roof_vertex_ids and edge[1] in roof_vertex_ids
    )
    roof_edge_ids = tuple(
        edge_id
        for edge_id in range(len(edges))
        if edge_id not in outline_edge_ids and edge_id not in ridge_edge_ids
    )
    outline_contour = find_outline_contour(edges, outline_edge_ids, outline_vertex_ids)

    return RoofGraphTopology(
        vertices=vertices,
        faces=normalized_faces,
        edges=edges,
        outline_edge_ids=tuple(outline_edge_ids),
        roof_edge_ids=roof_edge_ids,
        ridge_edge_ids=ridge_edge_ids,
        outline_vertex_ids=outline_vertex_ids,
        roof_vertex_ids=roof_vertex_ids,
        outline_contour=outline_contour,
    )


def extract_edges_from_faces(faces: FaceList) -> tuple[Edge, ...]:
    edges = {normalize_edge(edge) for face in faces for edge in face_to_edges(face)}
    return tuple(sorted(edges))


def remove_unreferenced_vertices(
    vertices: np.ndarray,
    edges: Sequence[Edge],
    faces: FaceList,
) -> tuple[np.ndarray, tuple[Edge, ...], tuple[tuple[int, ...], ...]]:
    referenced_edges = []
    for edge in edges:
        if find_edge_neighboring_faces(edge, faces):
            referenced_edges.append(normalize_edge(edge))
    if not referenced_edges:
        return vertices, tuple(), tuple()

    referenced_edge_set = tuple(sorted(set(referenced_edges)))
    referenced_vertex_ids = sorted({vertex_id for edge in referenced_edge_set for vertex_id in edge})
    if len(referenced_vertex_ids) == len(vertices):
        return vertices, referenced_edge_set, tuple(tuple(face) for face in faces if len(face) >= 3)

    vertex_id_map = {old_id: new_id for new_id, old_id in enumerate(referenced_vertex_ids)}
    remapped_vertices = vertices[np.asarray(referenced_vertex_ids)]
    remapped_edges = tuple((vertex_id_map[a], vertex_id_map[b]) for a, b in referenced_edge_set)
    remapped_faces = []
    for face in faces:
        filtered_face = [vertex_id_map[vertex_id] for vertex_id in face if vertex_id in vertex_id_map]
        if len(filtered_face) >= 3:
            remapped_faces.append(tuple(filtered_face))
    return remapped_vertices, remapped_edges, tuple(remapped_faces)


def face_to_edges(face: Sequence[int]) -> tuple[Edge, ...]:
    face = tuple(int(vertex_id) for vertex_id in face)
    return tuple(normalize_edge((face[index], face[(index + 1) % len(face)])) for index in range(len(face)))


def normalize_edge(edge: Sequence[int]) -> Edge:
    a, b = int(edge[0]), int(edge[1])
    return (a, b) if a <= b else (b, a)


def is_edge_in_face(edge: Sequence[int], face: Sequence[int]) -> bool:
    return normalize_edge(edge) in set(face_to_edges(face))


def find_edge_neighboring_faces(edge: Sequence[int], faces: FaceList) -> tuple[int, ...]:
    normalized_edge = normalize_edge(edge)
    neighboring_faces = []
    for face_id, face in enumerate(faces):
        if is_edge_in_face(normalized_edge, face):
            neighboring_faces.append(face_id)
    return tuple(neighboring_faces)


def find_outline_contour(
    edges: Sequence[Edge],
    outline_edge_ids: Sequence[int],
    outline_vertex_ids: Sequence[int],
) -> tuple[int, ...]:
    if not outline_vertex_ids:
        return tuple()

    start_vertex = outline_vertex_ids[0]
    contour = []
    current_vertex = start_vertex
    visited = set()
    while True:
        contour.append(current_vertex)
        visited.add(current_vertex)
        neighboring_outline_vertices = sorted(
            {
                vertex_id
                for edge_id in outline_edge_ids
                if current_vertex in edges[edge_id]
                for vertex_id in edges[edge_id]
                if vertex_id != current_vertex
            }
        )
        next_candidates = [vertex_id for vertex_id in neighboring_outline_vertices if vertex_id not in visited]
        if not next_candidates:
            break
        current_vertex = next_candidates[0]

    if set(contour) != set(outline_vertex_ids):
        raise ValueError("cannot find a valid outline contour")
    return tuple(contour)