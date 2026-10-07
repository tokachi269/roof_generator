from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


ROOF_ROLE_NONE = 0
ROOF_ROLE_EAVE = 1
ROOF_ROLE_GABLE_END = 2
ROOF_ROLE_SHED_LOW = 3
ROOF_ROLE_SHED_HIGH = 4
ROOF_ROLE_PARAPET = 5

EDGE_ROLE_EAVE = "eave"
EDGE_ROLE_GABLE_END = "gable_end"
EDGE_ROLE_IGNORE = "ignore"
EDGE_ROLE_SHED_HIGH = "shed_high"
EDGE_ROLE_SHED_LOW = "shed_low"

_EDGE_ROLE_NAME_BY_CODE = {
    ROOF_ROLE_NONE: EDGE_ROLE_IGNORE,
    ROOF_ROLE_EAVE: EDGE_ROLE_EAVE,
    ROOF_ROLE_GABLE_END: EDGE_ROLE_GABLE_END,
    ROOF_ROLE_SHED_LOW: EDGE_ROLE_SHED_LOW,
    ROOF_ROLE_SHED_HIGH: EDGE_ROLE_SHED_HIGH,
    ROOF_ROLE_PARAPET: "parapet",
}


@dataclass(frozen=True)
class GeneratedRoofGraph:
    vertices_2d: np.ndarray
    faces: tuple[tuple[int, ...], ...]
    edge_roles: tuple[str, ...]


def generate_rectangular_roof_graph_from_edge_roles(
    outline_vertices: np.ndarray,
    edge_roof_roles: Sequence[int | str],
) -> GeneratedRoofGraph:
    outline_vertices = np.asarray(outline_vertices, dtype=float)
    _validate_rectangular_outline(outline_vertices)
    normalized_roles = tuple(_normalize_edge_role(role) for role in edge_roof_roles)
    if len(normalized_roles) != 4:
        raise ValueError("rectangular roof generator requires exactly 4 edge roles")
    if "parapet" in normalized_roles:
        raise ValueError("rectangular roof generator does not support parapet edges yet")

    gable_edge_ids = tuple(index for index, role in enumerate(normalized_roles) if role == EDGE_ROLE_GABLE_END)
    if len(gable_edge_ids) == 2:
        eave_edge_ids = tuple(index for index, role in enumerate(normalized_roles) if role == EDGE_ROLE_EAVE)
        if len(eave_edge_ids) != 2:
            raise ValueError("rectangular gable input requires the remaining two edges to be eave")
        return generate_rectangular_gable_roof_graph(outline_vertices, normalized_roles)

    high_edge_ids = tuple(index for index, role in enumerate(normalized_roles) if role == EDGE_ROLE_SHED_HIGH)
    low_edge_ids = tuple(index for index, role in enumerate(normalized_roles) if role == EDGE_ROLE_SHED_LOW)
    if len(high_edge_ids) == 1 and len(low_edge_ids) == 1:
        allowed_side_roles = {EDGE_ROLE_IGNORE, EDGE_ROLE_EAVE}
        side_edge_ids = [
            index
            for index in range(4)
            if index not in high_edge_ids and index not in low_edge_ids
        ]
        if any(normalized_roles[index] not in allowed_side_roles for index in side_edge_ids):
            raise ValueError("rectangular shed input only supports eave or none on the remaining side edges")
        return generate_rectangular_shed_roof_graph(outline_vertices, normalized_roles)

    raise ValueError("unsupported rectangular edge-role combination for roof graph generation")


def generate_rectangular_gable_roof_graph(
    outline_vertices: np.ndarray,
    edge_roof_roles: Sequence[str],
) -> GeneratedRoofGraph:
    outline_vertices = np.asarray(outline_vertices, dtype=float)
    if outline_vertices.shape != (4, 2):
        raise ValueError("rectangular gable generator requires outline_vertices with shape (4, 2)")

    normalized_roles = tuple(str(role).strip().lower() for role in edge_roof_roles)
    if len(normalized_roles) != 4:
        raise ValueError("rectangular gable generator requires exactly 4 edge roles")

    gable_edge_ids = tuple(index for index, role in enumerate(normalized_roles) if role == EDGE_ROLE_GABLE_END)
    eave_edge_ids = tuple(index for index, role in enumerate(normalized_roles) if role == EDGE_ROLE_EAVE)
    if len(gable_edge_ids) != 2 or len(eave_edge_ids) != 2:
        raise ValueError("rectangular gable generator requires exactly 2 gable_end edges and 2 eave edges")
    if (gable_edge_ids[0] + 2) % 4 != gable_edge_ids[1]:
        raise ValueError("gable_end edges must be opposite edges of the outline")

    midpoint_vertices = []
    midpoint_vertex_ids = {}
    for edge_id in gable_edge_ids:
        vertex_id0 = edge_id
        vertex_id1 = (edge_id + 1) % 4
        midpoint = (outline_vertices[vertex_id0] + outline_vertices[vertex_id1]) / 2.0
        midpoint_vertex_ids[edge_id] = 4 + len(midpoint_vertices)
        midpoint_vertices.append(midpoint)

    all_vertices = np.vstack([outline_vertices, np.asarray(midpoint_vertices, dtype=float)])
    midpoint_id0 = midpoint_vertex_ids[gable_edge_ids[0]]
    midpoint_id1 = midpoint_vertex_ids[gable_edge_ids[1]]

    contour_path0 = _contour_path_between_edges(gable_edge_ids[0], gable_edge_ids[1])
    contour_path1 = _contour_path_between_edges(gable_edge_ids[1], gable_edge_ids[0])

    faces = (
        tuple(contour_path0 + [midpoint_id1, midpoint_id0]),
        tuple([midpoint_id0, midpoint_id1] + contour_path1),
        tuple([gable_edge_ids[0], midpoint_id0, (gable_edge_ids[0] + 1) % 4]),
        tuple([gable_edge_ids[1], midpoint_id1, (gable_edge_ids[1] + 1) % 4]),
    )
    return GeneratedRoofGraph(vertices_2d=all_vertices, faces=faces, edge_roles=normalized_roles)


def generate_rectangular_shed_roof_graph(
    outline_vertices: np.ndarray,
    edge_roof_roles: Sequence[str],
) -> GeneratedRoofGraph:
    outline_vertices = np.asarray(outline_vertices, dtype=float)
    if outline_vertices.shape != (4, 2):
        raise ValueError("rectangular shed generator requires outline_vertices with shape (4, 2)")

    normalized_roles = tuple(str(role).strip().lower() for role in edge_roof_roles)
    if len(normalized_roles) != 4:
        raise ValueError("rectangular shed generator requires exactly 4 edge roles")

    high_edge_ids = tuple(index for index, role in enumerate(normalized_roles) if role == EDGE_ROLE_SHED_HIGH)
    low_edge_ids = tuple(index for index, role in enumerate(normalized_roles) if role == EDGE_ROLE_SHED_LOW)
    if len(high_edge_ids) != 1 or len(low_edge_ids) != 1:
        raise ValueError("rectangular shed generator requires exactly one shed_high edge and one shed_low edge")
    if (low_edge_ids[0] + 2) % 4 != high_edge_ids[0]:
        raise ValueError("shed_high and shed_low edges must be opposite edges of the outline")

    high_edge_id = high_edge_ids[0]
    high_vertex_id0 = high_edge_id
    high_vertex_id1 = (high_edge_id + 1) % 4
    elevated_vertices = np.asarray(
        [
            outline_vertices[high_vertex_id0],
            outline_vertices[high_vertex_id1],
        ],
        dtype=float,
    )
    all_vertices = np.vstack([outline_vertices, elevated_vertices])
    elevated_vertex_id0 = 4
    elevated_vertex_id1 = 5

    low_edge_id = low_edge_ids[0]
    low_vertex_id0 = low_edge_id
    low_vertex_id1 = (low_edge_id + 1) % 4
    side_edge_id0 = (low_edge_id + 1) % 4
    side_edge_id1 = (high_edge_id + 2) % 4

    faces = (
        (low_vertex_id0, low_vertex_id1, elevated_vertex_id0, elevated_vertex_id1),
        (side_edge_id0, high_vertex_id0, elevated_vertex_id0),
        (elevated_vertex_id0, high_vertex_id0, high_vertex_id1, elevated_vertex_id1),
        (side_edge_id1, elevated_vertex_id1, high_vertex_id1),
    )
    return GeneratedRoofGraph(vertices_2d=all_vertices, faces=faces, edge_roles=normalized_roles)


def _contour_path_between_edges(start_edge_id: int, end_edge_id: int) -> list[int]:
    path = []
    vertex_id = (start_edge_id + 1) % 4
    while True:
        path.append(vertex_id)
        if vertex_id == end_edge_id:
            break
        vertex_id = (vertex_id + 1) % 4
    return path


def _normalize_edge_role(role: int | str) -> str:
    if isinstance(role, str):
        normalized_role = role.strip().lower()
        if normalized_role == "none":
            return EDGE_ROLE_IGNORE
        if normalized_role in _EDGE_ROLE_NAME_BY_CODE.values():
            return normalized_role
        raise ValueError(f"unsupported edge role '{role}'")

    try:
        role_code = int(role)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"unsupported edge role '{role}'") from exc
    if role_code not in _EDGE_ROLE_NAME_BY_CODE:
        raise ValueError(f"unsupported edge role code {role_code}")
    return _EDGE_ROLE_NAME_BY_CODE[role_code]


def _validate_rectangular_outline(outline_vertices: np.ndarray, tolerance: float = 1e-6) -> None:
    if outline_vertices.shape != (4, 2):
        raise ValueError("rectangular roof generator requires outline_vertices with shape (4, 2)")

    edge_vectors = []
    for index in range(4):
        vector = outline_vertices[(index + 1) % 4] - outline_vertices[index]
        length = float(np.linalg.norm(vector))
        if length <= tolerance:
            raise ValueError("rectangular roof generator requires non-degenerate outline edges")
        edge_vectors.append(vector / length)

    if abs(float(edge_vectors[0] @ edge_vectors[1])) > tolerance:
        raise ValueError("rectangular roof generator requires adjacent outline edges to be orthogonal")
    if 1.0 - abs(float(edge_vectors[0] @ edge_vectors[2])) > tolerance:
        raise ValueError("rectangular roof generator requires opposite outline edges to be parallel")
    if 1.0 - abs(float(edge_vectors[1] @ edge_vectors[3])) > tolerance:
        raise ValueError("rectangular roof generator requires opposite outline edges to be parallel")