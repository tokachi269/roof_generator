from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from enum import IntEnum
from typing import Sequence

import numpy as np


class UnsupportedTopologyError(ValueError):
    pass


class RoofRole(IntEnum):
    NONE = 0
    EAVE = 1
    GABLE_END = 2
    SHED_LOW = 3
    SHED_HIGH = 4
    PARAPET = 5


class PrimitiveKind(str, Enum):
    RECTANGLE = "rectangle"
    OBLIQUE_QUAD = "oblique_quad"
    RESIDUAL = "residual"


@dataclass(frozen=True)
class BoundaryEdge:
    v0: int
    v1: int
    role: RoofRole
    height: float | None = None
    pitch: float | None = None
    group: int = 0
    priority: int = 0


@dataclass(frozen=True)
class FootprintLoop:
    vertices: tuple[tuple[float, float], ...]
    boundary_edges: tuple[BoundaryEdge, ...]


@dataclass(frozen=True)
class RoofPrimitive:
    id: int
    kind: PrimitiveKind
    polygon: tuple[tuple[float, float], ...]
    boundary_edges: tuple[BoundaryEdge, ...]
    source_edges: tuple[int, ...]


@dataclass(frozen=True)
class RoofGraph:
    vertices_2d: np.ndarray
    faces: tuple[tuple[int, ...], ...]
    z_hints: dict[int, float]
    fixed_xy_vertex_ids: frozenset[int] = field(default_factory=frozenset)
    fixed_z_vertex_ids: frozenset[int] = field(default_factory=frozenset)
    edge_tags: dict[tuple[int, int], str] = field(default_factory=dict)
    primitive_kind: PrimitiveKind | None = None
    roof_kind: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "vertices_2d", np.asarray(self.vertices_2d, dtype=float))
        object.__setattr__(self, "faces", tuple(tuple(int(vertex_id) for vertex_id in face) for face in self.faces))
        object.__setattr__(self, "z_hints", {int(vertex_id): float(z_value) for vertex_id, z_value in self.z_hints.items()})
        object.__setattr__(self, "fixed_xy_vertex_ids", frozenset(int(vertex_id) for vertex_id in self.fixed_xy_vertex_ids))
        object.__setattr__(self, "fixed_z_vertex_ids", frozenset(int(vertex_id) for vertex_id in self.fixed_z_vertex_ids))
        object.__setattr__(
            self,
            "edge_tags",
            {tuple(sorted((int(edge[0]), int(edge[1])))): str(tag) for edge, tag in self.edge_tags.items()},
        )
        if self.vertices_2d.ndim != 2 or self.vertices_2d.shape[1] != 2:
            raise ValueError("vertices_2d must have shape (n, 2)")


_ROOF_ROLE_NAME = {
    RoofRole.NONE: "none",
    RoofRole.EAVE: "eave",
    RoofRole.GABLE_END: "gable_end",
    RoofRole.SHED_LOW: "shed_low",
    RoofRole.SHED_HIGH: "shed_high",
    RoofRole.PARAPET: "parapet",
}

_ROOF_ROLE_BY_NAME = {value: key for key, value in _ROOF_ROLE_NAME.items()}


def build_footprint_loop(
    vertices: Sequence[Sequence[float]],
    edge_roles: Sequence[RoofRole | int | str],
    edge_heights: Sequence[float | None] | None = None,
    edge_pitches: Sequence[float | None] | None = None,
    edge_groups: Sequence[int] | None = None,
    edge_priorities: Sequence[int] | None = None,
    tolerance: float = 1e-6,
) -> FootprintLoop:
    vertices_array = np.asarray(vertices, dtype=float)
    if vertices_array.ndim != 2 or vertices_array.shape[1] != 2:
        raise ValueError("vertices must have shape (n, 2)")
    if len(vertices_array) < 3:
        raise UnsupportedTopologyError("footprint requires at least three vertices")

    edge_count = len(vertices_array)
    roles = _normalize_role_sequence(edge_roles, edge_count)
    heights = _normalize_optional_float_sequence(edge_heights, edge_count)
    pitches = _normalize_optional_float_sequence(edge_pitches, edge_count)
    groups = _normalize_int_sequence(edge_groups, edge_count, default_value=0)
    priorities = _normalize_int_sequence(edge_priorities, edge_count, default_value=0)

    vertex_list = [tuple(vertex.tolist()) for vertex in vertices_array]
    edge_metadata = [
        {
            "role": roles[index],
            "height": heights[index],
            "pitch": pitches[index],
            "group": groups[index],
            "priority": priorities[index],
        }
        for index in range(edge_count)
    ]

    vertex_list, edge_metadata = _remove_collinear_vertices(vertex_list, edge_metadata, tolerance)
    _validate_edge_lengths(vertex_list, tolerance)
    _validate_simple_polygon(vertex_list, tolerance)
    if _signed_area(vertex_list) < 0.0:
        vertex_list, edge_metadata = _reverse_loop(vertex_list, edge_metadata)

    boundary_edges = tuple(
        BoundaryEdge(
            v0=index,
            v1=(index + 1) % len(vertex_list),
            role=edge_metadata[index]["role"],
            height=edge_metadata[index]["height"],
            pitch=edge_metadata[index]["pitch"],
            group=edge_metadata[index]["group"],
            priority=edge_metadata[index]["priority"],
        )
        for index in range(len(vertex_list))
    )
    return FootprintLoop(vertices=tuple(vertex_list), boundary_edges=boundary_edges)


def classify_primitive_kind(footprint: FootprintLoop, tolerance: float = 1e-6) -> PrimitiveKind:
    vertices = np.asarray(footprint.vertices, dtype=float)
    if len(vertices) != 4:
        return PrimitiveKind.RESIDUAL
    if not _is_convex_polygon(vertices, tolerance):
        return PrimitiveKind.RESIDUAL

    edge_vectors = _normalized_edge_vectors(vertices)
    if _is_parallel(edge_vectors[0], edge_vectors[2], tolerance) and _is_parallel(edge_vectors[1], edge_vectors[3], tolerance):
        if _is_orthogonal(edge_vectors[0], edge_vectors[1], tolerance):
            return PrimitiveKind.RECTANGLE
        return PrimitiveKind.OBLIQUE_QUAD
    return PrimitiveKind.RESIDUAL


def build_single_roof_primitive(footprint: FootprintLoop, primitive_id: int = 0) -> RoofPrimitive:
    return RoofPrimitive(
        id=int(primitive_id),
        kind=classify_primitive_kind(footprint),
        polygon=footprint.vertices,
        boundary_edges=footprint.boundary_edges,
        source_edges=tuple(range(len(footprint.boundary_edges))),
    )


def decompose_orthogonal_footprint_into_primitives(
    footprint: FootprintLoop,
    tolerance: float = 1e-6,
) -> tuple[RoofPrimitive, ...]:
    """Deprecated legacy preview; use roof_building for final meshes."""
    from .legacy_cell_preview import decompose_orthogonal_footprint_into_primitives as legacy
    return legacy(footprint=footprint, tolerance=tolerance)


def build_flat_roof_graph_from_primitives(
    primitives: Sequence[RoofPrimitive],
    roof_height: float,
) -> RoofGraph:
    """Deprecated legacy preview; use roof_building for final meshes."""
    from .legacy_cell_preview import build_flat_roof_graph_from_primitives as legacy
    return legacy(primitives=primitives, roof_height=roof_height)


def build_l_shaped_gable_roof_graph(
    footprint: FootprintLoop,
    roof_height: float,
    tolerance: float = 1e-6,
) -> RoofGraph:
    """Deprecated legacy preview; use roof_building for final meshes."""
    from .legacy_cell_preview import build_l_shaped_gable_roof_graph as legacy
    return legacy(footprint=footprint, roof_height=roof_height, tolerance=tolerance)


def build_orthogonal_gable_roof_graph(
    footprint: FootprintLoop,
    roof_height: float,
    gable_pair_mode: str = "shorter",
    tolerance: float = 1e-6,
) -> RoofGraph:
    """Deprecated legacy preview; use roof_building for final meshes."""
    from .legacy_cell_preview import build_orthogonal_gable_roof_graph as legacy
    return legacy(footprint=footprint, roof_height=roof_height, gable_pair_mode=gable_pair_mode, tolerance=tolerance)


def generate_single_primitive_roof_graph_from_edge_roles(
    outline_vertices: Sequence[Sequence[float]],
    edge_roof_roles: Sequence[RoofRole | int | str],
    roof_height: float,
) -> RoofGraph:
    footprint = build_footprint_loop(outline_vertices, edge_roof_roles)
    return build_single_primitive_roof_graph(footprint, roof_height=roof_height)


def build_single_primitive_roof_graph(footprint: FootprintLoop, roof_height: float) -> RoofGraph:
    primitive = build_single_roof_primitive(footprint)
    if primitive.kind == PrimitiveKind.RESIDUAL:
        raise UnsupportedTopologyError("single primitive generation supports only rectangle or oblique_quad footprints")

    roles = tuple(edge.role for edge in primitive.boundary_edges)
    if all(role in {RoofRole.NONE, RoofRole.PARAPET} for role in roles):
        return _build_flat_roof_graph(primitive, roof_height)
    if _is_gable_role_pattern(roles):
        return _build_gable_roof_graph(primitive, roof_height)
    if _is_shed_role_pattern(roles):
        return _build_shed_roof_graph(primitive, roof_height)
    raise UnsupportedTopologyError("unsupported single primitive edge-role combination")


def _build_flat_roof_graph(primitive: RoofPrimitive, roof_height: float) -> RoofGraph:
    vertices = np.asarray(primitive.polygon, dtype=float)
    face = tuple(range(len(vertices)))
    z_hints = {vertex_id: float(roof_height) for vertex_id in range(len(vertices))}
    edge_tags = {
        tuple(sorted((edge.v0, edge.v1))): _ROOF_ROLE_NAME[edge.role]
        for edge in primitive.boundary_edges
    }
    return RoofGraph(
        vertices_2d=vertices,
        faces=(face,),
        z_hints=z_hints,
        fixed_xy_vertex_ids=frozenset(range(len(vertices))),
        fixed_z_vertex_ids=frozenset(range(len(vertices))),
        edge_tags=edge_tags,
        primitive_kind=primitive.kind,
        roof_kind="flat",
    )


def _build_gable_roof_graph(primitive: RoofPrimitive, roof_height: float) -> RoofGraph:
    vertices = np.asarray(primitive.polygon, dtype=float)
    gable_edge_ids = tuple(index for index, edge in enumerate(primitive.boundary_edges) if edge.role == RoofRole.GABLE_END)
    if len(gable_edge_ids) != 2:
        raise UnsupportedTopologyError("gable generation requires exactly two gable_end edges")
    if (gable_edge_ids[0] + 2) % 4 != gable_edge_ids[1]:
        raise UnsupportedTopologyError("gable_end edges must be opposite edges")

    midpoint_vertices = []
    midpoint_vertex_ids = {}
    for edge_id in gable_edge_ids:
        vertex_id0 = edge_id
        vertex_id1 = (edge_id + 1) % 4
        midpoint = (vertices[vertex_id0] + vertices[vertex_id1]) / 2.0
        midpoint_vertex_ids[edge_id] = 4 + len(midpoint_vertices)
        midpoint_vertices.append(midpoint)

    all_vertices = np.vstack([vertices, np.asarray(midpoint_vertices, dtype=float)])
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
    z_hints = {vertex_id: 0.0 for vertex_id in range(4)}
    z_hints[midpoint_id0] = float(roof_height)
    z_hints[midpoint_id1] = float(roof_height)
    edge_tags = {
        tuple(sorted((edge.v0, edge.v1))): _ROOF_ROLE_NAME[edge.role]
        for edge in primitive.boundary_edges
    }
    edge_tags[(min(midpoint_id0, midpoint_id1), max(midpoint_id0, midpoint_id1))] = "ridge"
    return RoofGraph(
        vertices_2d=all_vertices,
        faces=faces,
        z_hints=z_hints,
        fixed_xy_vertex_ids=frozenset(range(4)),
        fixed_z_vertex_ids=frozenset(range(6)),
        edge_tags=edge_tags,
        primitive_kind=primitive.kind,
        roof_kind="gable",
    )


def _build_shed_roof_graph(primitive: RoofPrimitive, roof_height: float) -> RoofGraph:
    vertices = np.asarray(primitive.polygon, dtype=float)
    high_edge_ids = tuple(index for index, edge in enumerate(primitive.boundary_edges) if edge.role == RoofRole.SHED_HIGH)
    low_edge_ids = tuple(index for index, edge in enumerate(primitive.boundary_edges) if edge.role == RoofRole.SHED_LOW)
    if len(high_edge_ids) != 1 or len(low_edge_ids) != 1:
        raise UnsupportedTopologyError("shed generation requires exactly one shed_high edge and one shed_low edge")
    if (low_edge_ids[0] + 2) % 4 != high_edge_ids[0]:
        raise UnsupportedTopologyError("shed_high and shed_low edges must be opposite edges")

    high_edge_id = high_edge_ids[0]
    high_vertex_id0 = high_edge_id
    high_vertex_id1 = (high_edge_id + 1) % 4
    elevated_vertices = np.asarray([vertices[high_vertex_id0], vertices[high_vertex_id1]], dtype=float)
    all_vertices = np.vstack([vertices, elevated_vertices])
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
    z_hints = {vertex_id: 0.0 for vertex_id in range(4)}
    z_hints[elevated_vertex_id0] = float(roof_height)
    z_hints[elevated_vertex_id1] = float(roof_height)
    edge_tags = {
        tuple(sorted((edge.v0, edge.v1))): _ROOF_ROLE_NAME[edge.role]
        for edge in primitive.boundary_edges
    }
    return RoofGraph(
        vertices_2d=all_vertices,
        faces=faces,
        z_hints=z_hints,
        fixed_xy_vertex_ids=frozenset(range(4)),
        fixed_z_vertex_ids=frozenset(range(6)),
        edge_tags=edge_tags,
        primitive_kind=primitive.kind,
        roof_kind="shed",
    )


def _is_gable_role_pattern(roles: Sequence[RoofRole]) -> bool:
    gable_edge_ids = tuple(index for index, role in enumerate(roles) if role == RoofRole.GABLE_END)
    if len(gable_edge_ids) != 2:
        return False
    if (gable_edge_ids[0] + 2) % 4 != gable_edge_ids[1]:
        return False
    return all(role in {RoofRole.EAVE, RoofRole.GABLE_END} for role in roles)


def _is_shed_role_pattern(roles: Sequence[RoofRole]) -> bool:
    high_edge_ids = tuple(index for index, role in enumerate(roles) if role == RoofRole.SHED_HIGH)
    low_edge_ids = tuple(index for index, role in enumerate(roles) if role == RoofRole.SHED_LOW)
    if len(high_edge_ids) != 1 or len(low_edge_ids) != 1:
        return False
    if (low_edge_ids[0] + 2) % 4 != high_edge_ids[0]:
        return False
    for index, role in enumerate(roles):
        if index in high_edge_ids or index in low_edge_ids:
            continue
        if role not in {RoofRole.NONE, RoofRole.EAVE}:
            return False
    return True


def _normalize_role_sequence(raw_roles: Sequence[RoofRole | int | str], expected_count: int) -> tuple[RoofRole, ...]:
    if len(raw_roles) != expected_count:
        raise ValueError(f"edge role count must match vertex count ({expected_count})")
    return tuple(_normalize_role(role) for role in raw_roles)


def _normalize_role(raw_role: RoofRole | int | str) -> RoofRole:
    if isinstance(raw_role, RoofRole):
        return raw_role
    if isinstance(raw_role, str):
        normalized = raw_role.strip().lower()
        if normalized in {"ignore", "none"}:
            return RoofRole.NONE
        try:
            return _ROOF_ROLE_BY_NAME[normalized]
        except KeyError as exc:
            raise ValueError(f"unsupported roof role '{raw_role}'") from exc
    try:
        return RoofRole(int(raw_role))
    except ValueError as exc:
        raise ValueError(f"unsupported roof role '{raw_role}'") from exc


def _normalize_optional_float_sequence(values: Sequence[float | None] | None, expected_count: int) -> tuple[float | None, ...]:
    if values is None:
        return tuple(None for _ in range(expected_count))
    if len(values) != expected_count:
        raise ValueError(f"value count must match vertex count ({expected_count})")
    normalized = []
    for value in values:
        normalized.append(None if value is None else float(value))
    return tuple(normalized)


def _normalize_int_sequence(values: Sequence[int] | None, expected_count: int, default_value: int) -> tuple[int, ...]:
    if values is None:
        return tuple(default_value for _ in range(expected_count))
    if len(values) != expected_count:
        raise ValueError(f"value count must match vertex count ({expected_count})")
    return tuple(int(value) for value in values)


def _remove_collinear_vertices(vertex_list, edge_metadata, tolerance: float):
    changed = True
    while changed and len(vertex_list) > 3:
        changed = False
        count = len(vertex_list)
        for index in range(count):
            previous_index = (index - 1) % count
            next_index = (index + 1) % count
            if not _is_collinear(vertex_list[previous_index], vertex_list[index], vertex_list[next_index], tolerance):
                continue
            if not _metadata_matches(edge_metadata[previous_index], edge_metadata[index]):
                continue
            del vertex_list[index]
            del edge_metadata[index]
            changed = True
            break
    return vertex_list, edge_metadata


def _validate_edge_lengths(vertex_list, tolerance: float) -> None:
    for index in range(len(vertex_list)):
        vertex0 = np.asarray(vertex_list[index], dtype=float)
        vertex1 = np.asarray(vertex_list[(index + 1) % len(vertex_list)], dtype=float)
        if float(np.linalg.norm(vertex1 - vertex0)) <= tolerance:
            raise UnsupportedTopologyError("footprint contains an edge that is too short")


def _validate_simple_polygon(vertex_list, tolerance: float) -> None:
    edge_count = len(vertex_list)
    for edge_id0 in range(edge_count):
        segment0 = (vertex_list[edge_id0], vertex_list[(edge_id0 + 1) % edge_count])
        for edge_id1 in range(edge_id0 + 1, edge_count):
            if edge_id1 == edge_id0:
                continue
            if edge_id1 == (edge_id0 + 1) % edge_count:
                continue
            if edge_id0 == (edge_id1 + 1) % edge_count:
                continue
            segment1 = (vertex_list[edge_id1], vertex_list[(edge_id1 + 1) % edge_count])
            if _segments_intersect(segment0, segment1, tolerance):
                raise UnsupportedTopologyError("footprint polygon must not self-intersect")


def _reverse_loop(vertex_list, edge_metadata):
    reversed_vertices = list(reversed(vertex_list))
    edge_count = len(edge_metadata)
    reversed_metadata = [edge_metadata[(edge_count - 2 - index) % edge_count] for index in range(edge_count)]
    return reversed_vertices, reversed_metadata


def _is_collinear(vertex0, vertex1, vertex2, tolerance: float) -> bool:
    vector0 = np.asarray(vertex1, dtype=float) - np.asarray(vertex0, dtype=float)
    vector1 = np.asarray(vertex2, dtype=float) - np.asarray(vertex1, dtype=float)
    cross_value = abs(_cross2d(vector0, vector1))
    if cross_value > tolerance:
        return False
    return float(vector0 @ vector1) >= 0.0


def _metadata_matches(metadata0: dict, metadata1: dict) -> bool:
    if metadata0["role"] != metadata1["role"]:
        return False
    if metadata0["group"] != metadata1["group"] or metadata0["priority"] != metadata1["priority"]:
        return False
    for key in ("height", "pitch"):
        value0 = metadata0[key]
        value1 = metadata1[key]
        if value0 is None or value1 is None:
            if value0 is not value1:
                return False
            continue
        if abs(float(value0) - float(value1)) > 1e-9:
            return False
    return True


def _signed_area(vertices) -> float:
    area = 0.0
    for index, vertex in enumerate(vertices):
        x0, y0 = vertex
        x1, y1 = vertices[(index + 1) % len(vertices)]
        area += x0 * y1 - x1 * y0
    return area * 0.5


def _segments_intersect(segment0, segment1, tolerance: float) -> bool:
    p0 = np.asarray(segment0[0], dtype=float)
    p1 = np.asarray(segment0[1], dtype=float)
    q0 = np.asarray(segment1[0], dtype=float)
    q1 = np.asarray(segment1[1], dtype=float)

    def _orientation(a, b, c):
        return _cross2d(b - a, c - a)

    o0 = _orientation(p0, p1, q0)
    o1 = _orientation(p0, p1, q1)
    o2 = _orientation(q0, q1, p0)
    o3 = _orientation(q0, q1, p1)

    if (o0 > tolerance and o1 < -tolerance or o0 < -tolerance and o1 > tolerance) and (
        o2 > tolerance and o3 < -tolerance or o2 < -tolerance and o3 > tolerance
    ):
        return True

    if abs(o0) <= tolerance and _point_on_segment(q0, p0, p1, tolerance):
        return True
    if abs(o1) <= tolerance and _point_on_segment(q1, p0, p1, tolerance):
        return True
    if abs(o2) <= tolerance and _point_on_segment(p0, q0, q1, tolerance):
        return True
    if abs(o3) <= tolerance and _point_on_segment(p1, q0, q1, tolerance):
        return True
    return False


def _point_on_segment(point, segment_start, segment_end, tolerance: float) -> bool:
    min_x = min(segment_start[0], segment_end[0]) - tolerance
    max_x = max(segment_start[0], segment_end[0]) + tolerance
    min_y = min(segment_start[1], segment_end[1]) - tolerance
    max_y = max(segment_start[1], segment_end[1]) + tolerance
    return min_x <= point[0] <= max_x and min_y <= point[1] <= max_y


def _is_convex_polygon(vertices: np.ndarray, tolerance: float) -> bool:
    cross_sign = 0.0
    for index in range(len(vertices)):
        vertex0 = vertices[index]
        vertex1 = vertices[(index + 1) % len(vertices)]
        vertex2 = vertices[(index + 2) % len(vertices)]
        cross_value = _cross2d(vertex1 - vertex0, vertex2 - vertex1)
        if abs(cross_value) <= tolerance:
            continue
        if cross_sign == 0.0:
            cross_sign = cross_value
            continue
        if cross_sign * cross_value < 0.0:
            return False
    return cross_sign != 0.0


def _normalized_edge_vectors(vertices: np.ndarray) -> tuple[np.ndarray, ...]:
    vectors = []
    for index in range(len(vertices)):
        vector = vertices[(index + 1) % len(vertices)] - vertices[index]
        length = float(np.linalg.norm(vector))
        if length == 0.0:
            raise UnsupportedTopologyError("primitive contains a degenerate edge")
        vectors.append(vector / length)
    return tuple(vectors)


def _is_parallel(vector0: np.ndarray, vector1: np.ndarray, tolerance: float) -> bool:
    return abs(_cross2d(vector0, vector1)) <= tolerance


def _is_orthogonal(vector0: np.ndarray, vector1: np.ndarray, tolerance: float) -> bool:
    return abs(float(vector0 @ vector1)) <= tolerance


def _cross2d(vector0: np.ndarray, vector1: np.ndarray) -> float:
    return float(vector0[0] * vector1[1] - vector0[1] * vector1[0])


def _contour_path_between_edges(start_edge_id: int, end_edge_id: int) -> list[int]:
    path = []
    vertex_id = (start_edge_id + 1) % 4
    while True:
        path.append(vertex_id)
        if vertex_id == end_edge_id:
            break
        vertex_id = (vertex_id + 1) % 4
    return path
