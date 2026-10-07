"""Deprecated cell/residual preview. Never imported by final roof generation.

Retained solely for existing preview workflows and baseline regression.
"""
from __future__ import annotations
import numpy as np
from typing import Sequence
from .roof_topology_generator import (BoundaryEdge, FootprintLoop, RoofPrimitive, RoofGraph, RoofRole, PrimitiveKind, UnsupportedTopologyError,
_cross2d,
build_footprint_loop,
build_single_roof_primitive,
classify_primitive_kind)

def decompose_orthogonal_footprint_into_primitives(
    footprint: FootprintLoop,
    tolerance: float = 1e-6,
) -> tuple[RoofPrimitive, ...]:
    primitive_kind = classify_primitive_kind(footprint, tolerance=tolerance)
    if primitive_kind in {PrimitiveKind.RECTANGLE, PrimitiveKind.OBLIQUE_QUAD}:
        return (build_single_roof_primitive(footprint),)

    vertices = np.asarray(footprint.vertices, dtype=float)
    local_vertices, origin, axis_u, axis_v = _build_orthogonal_frame(vertices, tolerance=tolerance)

    occupied_cells = _rasterize_axis_aligned_polygon_to_cells(local_vertices, tolerance=tolerance)
    if not occupied_cells:
        raise UnsupportedTopologyError("orthogonal primitive decomposition requires a positive-area footprint")

    rectangles = _decompose_cells_into_max_rectangles(occupied_cells)
    primitives = []
    for primitive_id, rectangle in enumerate(rectangles):
        local_polygon = np.asarray(_rectangle_polygon_from_cell_rectangle(rectangle), dtype=float)
        polygon = _lift_orthogonal_points(local_polygon, origin, axis_u, axis_v)
        primitive_footprint = build_footprint_loop(polygon, [RoofRole.NONE] * 4, tolerance=tolerance)
        primitives.append(build_single_roof_primitive(primitive_footprint, primitive_id=primitive_id))
    return tuple(primitives)

def build_flat_roof_graph_from_primitives(
    primitives: Sequence[RoofPrimitive],
    roof_height: float,
) -> RoofGraph:
    vertices = []
    faces = []
    z_hints = {}
    vertex_ids_by_position = {}
    for primitive in primitives:
        face = []
        for vertex in primitive.polygon:
            position = (float(vertex[0]), float(vertex[1]))
            vertex_id = vertex_ids_by_position.get(position)
            if vertex_id is None:
                vertex_id = len(vertices)
                vertex_ids_by_position[position] = vertex_id
                vertices.append(position)
                z_hints[vertex_id] = float(roof_height)
            face.append(vertex_id)
        faces.append(face)
    return RoofGraph(
        vertices_2d=np.asarray(vertices, dtype=float),
        faces=tuple(tuple(face) for face in faces),
        z_hints=z_hints,
        fixed_xy_vertex_ids=frozenset(range(len(vertices))),
        fixed_z_vertex_ids=frozenset(range(len(vertices))),
        primitive_kind=PrimitiveKind.RESIDUAL,
        roof_kind="flat",
    )

def build_l_shaped_gable_roof_graph(
    footprint: FootprintLoop,
    roof_height: float,
    tolerance: float = 1e-6,
) -> RoofGraph:
    vertices = np.asarray(footprint.vertices, dtype=float)
    if len(vertices) != 6:
        raise UnsupportedTopologyError("L-shaped gable generation requires a six-vertex orthogonal outline")
    if not _is_axis_aligned_loop(vertices, tolerance):
        raise UnsupportedTopologyError("L-shaped gable generation requires an axis-aligned footprint")

    reflex_vertex_ids = _find_reflex_vertex_ids(vertices, tolerance)
    if len(reflex_vertex_ids) != 1:
        raise UnsupportedTopologyError("L-shaped gable generation requires exactly one reflex corner")
    reflex_id = reflex_vertex_ids[0]

    cap_edge_ids = ((reflex_id - 2) % 6, (reflex_id + 1) % 6)
    _validate_l_shaped_gable_roles(footprint, cap_edge_ids)

    wing_side_edge_ids0 = ((reflex_id - 1) % 6, (reflex_id + 3) % 6)
    wing_side_edge_ids1 = (reflex_id % 6, (reflex_id + 2) % 6)
    ridge_axis0, ridge_value0 = _axis_aligned_midline(vertices, wing_side_edge_ids0, tolerance)
    ridge_axis1, ridge_value1 = _axis_aligned_midline(vertices, wing_side_edge_ids1, tolerance)
    if ridge_axis0 == ridge_axis1:
        raise UnsupportedTopologyError("L-shaped gable generation requires perpendicular wings")
    junction = np.empty(2, dtype=float)
    junction[ridge_axis0] = ridge_value0
    junction[ridge_axis1] = ridge_value1
    if not _point_in_polygon_2d(junction, vertices, tolerance):
        raise UnsupportedTopologyError("L-shaped gable ridge junction fell outside the footprint")

    cap_midpoints = []
    for cap_edge_id in cap_edge_ids:
        midpoint = (vertices[cap_edge_id] + vertices[(cap_edge_id + 1) % 6]) / 2.0
        if float(np.linalg.norm(junction - midpoint)) <= tolerance:
            raise UnsupportedTopologyError("L-shaped gable generation produced a degenerate ridge")
        cap_midpoints.append(midpoint)

    all_vertices = np.vstack([vertices, np.asarray(cap_midpoints, dtype=float), junction[np.newaxis, :]])
    midpoint_id0 = 6
    midpoint_id1 = 7
    junction_id = 8
    faces = (
        ((reflex_id + 3) % 6, (reflex_id + 4) % 6, midpoint_id0, junction_id),
        ((reflex_id - 2) % 6, (reflex_id - 1) % 6, midpoint_id0),
        ((reflex_id - 1) % 6, reflex_id, junction_id, midpoint_id0),
        (reflex_id, (reflex_id + 1) % 6, midpoint_id1, junction_id),
        ((reflex_id + 1) % 6, (reflex_id + 2) % 6, midpoint_id1),
        ((reflex_id + 2) % 6, (reflex_id + 3) % 6, junction_id, midpoint_id1),
    )
    z_hints = {vertex_id: 0.0 for vertex_id in range(6)}
    z_hints[midpoint_id0] = float(roof_height)
    z_hints[midpoint_id1] = float(roof_height)
    z_hints[junction_id] = float(roof_height)
    edge_tags = {}
    for edge_id, edge in enumerate(footprint.boundary_edges):
        tag = "gable_end" if edge_id in cap_edge_ids else "eave"
        edge_tags[tuple(sorted((edge.v0, edge.v1)))] = tag
    edge_tags[(midpoint_id0, junction_id)] = "ridge"
    edge_tags[(midpoint_id1, junction_id)] = "ridge"
    return RoofGraph(
        vertices_2d=all_vertices,
        faces=faces,
        z_hints=z_hints,
        fixed_xy_vertex_ids=frozenset(range(6)),
        fixed_z_vertex_ids=frozenset(range(8)),
        edge_tags=edge_tags,
        primitive_kind=PrimitiveKind.RESIDUAL,
        roof_kind="gable",
    )

def build_orthogonal_gable_roof_graph(
    footprint: FootprintLoop,
    roof_height: float,
    gable_pair_mode: str = "shorter",
    tolerance: float = 1e-6,
) -> RoofGraph:
    """Build a cross-gable roof over an arbitrary orthogonal residual outline.

    Terminal gable caps are derived from the rectangular primitive
    decomposition.  All remaining outline edges act as eaves.  Each occupied
    orthogonal cell contributes a conforming triangular fan: eave samples stay
    at zero and shared/cap samples use the requested ridge height.  This keeps
    the preview continuous without encoding a particular vertex count or
    reflex-corner layout.
    """
    source_vertices = np.asarray(footprint.vertices, dtype=float)
    vertices, origin, axis_u, axis_v = _build_orthogonal_frame(source_vertices, tolerance=tolerance)
    aligned_footprint = FootprintLoop(
        vertices=tuple(tuple(float(value) for value in vertex) for vertex in vertices),
        boundary_edges=footprint.boundary_edges,
    )
    if gable_pair_mode not in {"shorter", "longer"}:
        raise ValueError("gable_pair_mode must be 'shorter' or 'longer'")

    occupied_cells = _rasterize_axis_aligned_polygon_to_cells(vertices, tolerance=tolerance)
    if not occupied_cells:
        raise UnsupportedTopologyError("orthogonal gable generation requires a positive-area footprint")
    primitives = decompose_orthogonal_footprint_into_primitives(aligned_footprint, tolerance=tolerance)
    gable_edge_ids = _resolve_orthogonal_gable_cap_edge_ids(
        aligned_footprint,
        primitives,
        gable_pair_mode=gable_pair_mode,
        tolerance=tolerance,
    )
    if not gable_edge_ids:
        raise UnsupportedTopologyError("orthogonal gable generation could not identify a terminal gable edge")

    eave_segments = []
    for edge_id, edge in enumerate(aligned_footprint.boundary_edges):
        if edge_id in gable_edge_ids:
            continue
        if edge.role not in {RoofRole.NONE, RoofRole.EAVE, RoofRole.PARAPET}:
            raise UnsupportedTopologyError("orthogonal gable generation supports only eave or gable_end boundary roles")
        eave_segments.append((vertices[edge.v0], vertices[edge.v1]))
    if not eave_segments:
        raise UnsupportedTopologyError("orthogonal gable generation requires at least one eave edge")

    graph_vertices = []
    vertex_id_by_position = {}

    def vertex_id_for(point) -> int:
        point_array = np.asarray(point, dtype=float)
        is_eave = any(
            _point_on_segment_2d(point_array, segment0, segment1, tolerance=tolerance)
            for segment0, segment1 in eave_segments
        )
        z_value = 0.0 if is_eave else float(roof_height)
        key = (
            int(round(float(point_array[0]) / tolerance)),
            int(round(float(point_array[1]) / tolerance)),
            int(round(z_value / tolerance)),
        )
        vertex_id = vertex_id_by_position.get(key)
        if vertex_id is None:
            vertex_id = len(graph_vertices)
            vertex_id_by_position[key] = vertex_id
            graph_vertices.append((float(point_array[0]), float(point_array[1]), z_value))
        return vertex_id

    surface_faces = []
    for cell in sorted(occupied_cells, key=lambda value: (value[2], value[0], value[3], value[1])):
        x0, x1, y0, y1 = cell
        perimeter = (
            (x0, y0),
            ((x0 + x1) * 0.5, y0),
            (x1, y0),
            (x1, (y0 + y1) * 0.5),
            (x1, y1),
            ((x0 + x1) * 0.5, y1),
            (x0, y1),
            (x0, (y0 + y1) * 0.5),
        )
        perimeter_vertex_ids = tuple(vertex_id_for(point) for point in perimeter)
        center_vertex_id = vertex_id_for(((x0 + x1) * 0.5, (y0 + y1) * 0.5))
        for index in range(0, len(perimeter_vertex_ids), 2):
            corner_id = perimeter_vertex_ids[index]
            next_midpoint_id = perimeter_vertex_ids[(index + 1) % len(perimeter_vertex_ids)]
            previous_midpoint_id = perimeter_vertex_ids[(index - 1) % len(perimeter_vertex_ids)]
            quad = (corner_id, next_midpoint_id, center_vertex_id, previous_midpoint_id)
            quad_height_error = abs(
                graph_vertices[corner_id][2]
                + graph_vertices[center_vertex_id][2]
                - graph_vertices[next_midpoint_id][2]
                - graph_vertices[previous_midpoint_id][2]
            )
            if quad_height_error <= tolerance:
                surface_faces.append(quad)
            else:
                surface_faces.append((corner_id, next_midpoint_id, center_vertex_id))
                surface_faces.append((corner_id, center_vertex_id, previous_midpoint_id))

    faces = list(surface_faces)
    for edge_id in sorted(gable_edge_ids):
        edge = aligned_footprint.boundary_edges[edge_id]
        cap_vertex_ids = _vertices_on_segment(
            graph_vertices,
            vertices[edge.v0],
            vertices[edge.v1],
            tolerance=tolerance,
        )
        if len(cap_vertex_ids) >= 3 and max(graph_vertices[vertex_id][2] for vertex_id in cap_vertex_ids) > tolerance:
            faces.append(tuple(cap_vertex_ids))

    local_vertices_2d = np.asarray([(vertex[0], vertex[1]) for vertex in graph_vertices], dtype=float)
    vertices_2d = _lift_orthogonal_points(local_vertices_2d, origin, axis_u, axis_v)
    z_hints = {vertex_id: float(vertex[2]) for vertex_id, vertex in enumerate(graph_vertices)}
    boundary_vertex_ids = frozenset(
        vertex_id
        for vertex_id, vertex in enumerate(graph_vertices)
        if _point_on_any_boundary_segment(np.asarray(vertex[:2]), aligned_footprint, tolerance=tolerance)
    )
    outline_base_vertex_ids = frozenset(
        vertex_id for vertex_id in boundary_vertex_ids if abs(graph_vertices[vertex_id][2]) <= tolerance
    )
    edge_tags = {}
    for edge_id, edge in enumerate(aligned_footprint.boundary_edges):
        tag = "gable_end" if edge_id in gable_edge_ids else "eave"
        segment_vertex_ids = _vertices_on_segment(
            graph_vertices,
            vertices[edge.v0],
            vertices[edge.v1],
            tolerance=tolerance,
        )
        if edge_id in gable_edge_ids:
            edge_tags[tuple(sorted((segment_vertex_ids[0], segment_vertex_ids[-1])))] = tag
        else:
            for index in range(len(segment_vertex_ids) - 1):
                edge_tags[tuple(sorted((segment_vertex_ids[index], segment_vertex_ids[index + 1])))] = tag
    return RoofGraph(
        vertices_2d=vertices_2d,
        faces=tuple(faces),
        z_hints=z_hints,
        fixed_xy_vertex_ids=outline_base_vertex_ids,
        fixed_z_vertex_ids=boundary_vertex_ids,
        edge_tags=edge_tags,
        primitive_kind=PrimitiveKind.RESIDUAL,
        roof_kind="gable",
    )

def _find_reflex_vertex_ids(vertices: np.ndarray, tolerance: float) -> tuple[int, ...]:
    reflex_ids = []
    count = len(vertices)
    for index in range(count):
        previous_vector = vertices[index] - vertices[(index - 1) % count]
        next_vector = vertices[(index + 1) % count] - vertices[index]
        if _cross2d(previous_vector, next_vector) < -tolerance:
            reflex_ids.append(index)
    return tuple(reflex_ids)

def _validate_l_shaped_gable_roles(footprint: FootprintLoop, cap_edge_ids: tuple[int, int]) -> None:
    for edge_id, edge in enumerate(footprint.boundary_edges):
        if edge_id in cap_edge_ids:
            allowed_roles = {RoofRole.NONE, RoofRole.GABLE_END}
        else:
            allowed_roles = {RoofRole.NONE, RoofRole.EAVE}
        if edge.role not in allowed_roles:
            raise UnsupportedTopologyError(
                "L-shaped gable generation requires gable_end roles only on the two wing-end edges"
            )

def _resolve_orthogonal_gable_cap_edge_ids(
    footprint: FootprintLoop,
    primitives: Sequence[RoofPrimitive],
    gable_pair_mode: str,
    tolerance: float,
) -> frozenset[int]:
    explicit_gable_ids = frozenset(
        edge_id for edge_id, edge in enumerate(footprint.boundary_edges) if edge.role == RoofRole.GABLE_END
    )
    if explicit_gable_ids:
        invalid_roles = [
            edge.role
            for edge in footprint.boundary_edges
            if edge.role not in {RoofRole.NONE, RoofRole.EAVE, RoofRole.GABLE_END, RoofRole.PARAPET}
        ]
        if invalid_roles:
            raise UnsupportedTopologyError("orthogonal gable generation received incompatible boundary roles")
        return explicit_gable_ids

    footprint_vertices = np.asarray(footprint.vertices, dtype=float)
    cap_edge_ids = set()
    for primitive in primitives:
        polygon = np.asarray(primitive.polygon, dtype=float)
        edge_lengths = tuple(
            float(np.linalg.norm(polygon[(edge_id + 1) % 4] - polygon[edge_id]))
            for edge_id in range(4)
        )
        pair_lengths = (edge_lengths[0], edge_lengths[1])
        target_pair = 0 if pair_lengths[0] <= pair_lengths[1] else 1
        if gable_pair_mode == "longer":
            target_pair = 1 - target_pair
        primitive_cap_edge_ids = (0, 2) if target_pair == 0 else (1, 3)
        for primitive_edge_id in primitive_cap_edge_ids:
            segment0 = polygon[primitive_edge_id]
            segment1 = polygon[(primitive_edge_id + 1) % 4]
            for footprint_edge_id, footprint_edge in enumerate(footprint.boundary_edges):
                boundary0 = footprint_vertices[footprint_edge.v0]
                boundary1 = footprint_vertices[footprint_edge.v1]
                if _segments_match(segment0, segment1, boundary0, boundary1, tolerance=tolerance):
                    cap_edge_ids.add(footprint_edge_id)
                    break
    return frozenset(cap_edge_ids)

def _segments_match(segment0, segment1, candidate0, candidate1, tolerance: float) -> bool:
    return (
        np.linalg.norm(np.asarray(segment0) - np.asarray(candidate0)) <= tolerance
        and np.linalg.norm(np.asarray(segment1) - np.asarray(candidate1)) <= tolerance
    ) or (
        np.linalg.norm(np.asarray(segment0) - np.asarray(candidate1)) <= tolerance
        and np.linalg.norm(np.asarray(segment1) - np.asarray(candidate0)) <= tolerance
    )

def _vertices_on_segment(graph_vertices, segment0, segment1, tolerance: float) -> list[int]:
    segment0 = np.asarray(segment0, dtype=float)
    segment1 = np.asarray(segment1, dtype=float)
    vector = segment1 - segment0
    squared_length = float(np.dot(vector, vector))
    matches = []
    for vertex_id, vertex in enumerate(graph_vertices):
        point = np.asarray(vertex[:2], dtype=float)
        if not _point_on_segment_2d(point, segment0, segment1, tolerance=tolerance):
            continue
        amount = 0.0 if squared_length <= tolerance * tolerance else float(np.dot(point - segment0, vector) / squared_length)
        matches.append((amount, vertex_id))
    matches.sort(key=lambda item: item[0])
    return [vertex_id for _amount, vertex_id in matches]

def _point_on_segment_2d(point, segment0, segment1, tolerance: float) -> bool:
    vector = np.asarray(segment1, dtype=float) - np.asarray(segment0, dtype=float)
    relative = np.asarray(point, dtype=float) - np.asarray(segment0, dtype=float)
    if abs(_cross2d(vector, relative)) > tolerance * max(1.0, float(np.linalg.norm(vector))):
        return False
    dot = float(np.dot(relative, vector))
    squared_length = float(np.dot(vector, vector))
    return -tolerance <= dot <= squared_length + tolerance

def _point_on_any_boundary_segment(point: np.ndarray, footprint: FootprintLoop, tolerance: float) -> bool:
    vertices = np.asarray(footprint.vertices, dtype=float)
    return any(
        _point_on_segment_2d(point, vertices[edge.v0], vertices[edge.v1], tolerance=tolerance)
        for edge in footprint.boundary_edges
    )

def _axis_aligned_midline(vertices: np.ndarray, edge_ids: tuple[int, int], tolerance: float) -> tuple[int, float]:
    fixed_axes = []
    values = []
    count = len(vertices)
    for edge_id in edge_ids:
        vector = vertices[(edge_id + 1) % count] - vertices[edge_id]
        if abs(float(vector[1])) <= tolerance:
            fixed_axes.append(1)
            values.append(float(vertices[edge_id][1]))
        elif abs(float(vector[0])) <= tolerance:
            fixed_axes.append(0)
            values.append(float(vertices[edge_id][0]))
        else:
            raise UnsupportedTopologyError("L-shaped gable generation requires axis-aligned wing sides")
    if fixed_axes[0] != fixed_axes[1]:
        raise UnsupportedTopologyError("L-shaped gable wing sides must be parallel")
    return fixed_axes[0], (values[0] + values[1]) / 2.0

def _is_axis_aligned_loop(vertices: np.ndarray, tolerance: float) -> bool:
    for index in range(len(vertices)):
        vector = vertices[(index + 1) % len(vertices)] - vertices[index]
        if abs(float(vector[0])) <= tolerance or abs(float(vector[1])) <= tolerance:
            continue
        return False
    return True

def _build_orthogonal_frame(
    vertices: np.ndarray,
    tolerance: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    vertices = np.asarray(vertices, dtype=float)
    if len(vertices) < 3:
        raise UnsupportedTopologyError("orthogonal footprint requires at least three vertices")
    origin = np.asarray(vertices[0], dtype=float)
    first_edge = np.asarray(vertices[1], dtype=float) - origin
    first_edge_length = float(np.linalg.norm(first_edge))
    if first_edge_length <= tolerance:
        raise UnsupportedTopologyError("orthogonal footprint contains a degenerate first edge")
    axis_u = first_edge / first_edge_length
    axis_v = np.asarray((-axis_u[1], axis_u[0]), dtype=float)
    offsets = vertices - origin
    local_vertices = np.column_stack((offsets @ axis_u, offsets @ axis_v))
    if not _is_axis_aligned_loop(local_vertices, tolerance=tolerance):
        raise UnsupportedTopologyError("orthogonal topology generation requires an orthogonal footprint")
    local_vertices[:, 0] = _snap_coordinate_levels(local_vertices[:, 0], tolerance=tolerance)
    local_vertices[:, 1] = _snap_coordinate_levels(local_vertices[:, 1], tolerance=tolerance)
    return local_vertices, origin, axis_u, axis_v

def _snap_coordinate_levels(values: np.ndarray, tolerance: float) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    levels = []
    for value in sorted(float(item) for item in values):
        if levels and abs(value - levels[-1][-1]) <= tolerance:
            levels[-1].append(value)
        else:
            levels.append([value])
    representatives = [float(sum(level) / len(level)) for level in levels]
    return np.asarray(
        [min(representatives, key=lambda representative: abs(float(value) - representative)) for value in values],
        dtype=float,
    )

def _lift_orthogonal_points(
    local_points: np.ndarray,
    origin: np.ndarray,
    axis_u: np.ndarray,
    axis_v: np.ndarray,
) -> np.ndarray:
    local_points = np.asarray(local_points, dtype=float)
    return (
        np.asarray(origin, dtype=float)[np.newaxis, :]
        + local_points[:, 0, np.newaxis] * np.asarray(axis_u, dtype=float)[np.newaxis, :]
        + local_points[:, 1, np.newaxis] * np.asarray(axis_v, dtype=float)[np.newaxis, :]
    )

def _rasterize_axis_aligned_polygon_to_cells(vertices: np.ndarray, tolerance: float) -> set[tuple[float, float, float, float]]:
    x_values = sorted({float(value) for value in vertices[:, 0]})
    y_values = sorted({float(value) for value in vertices[:, 1]})
    occupied = set()
    for x_index in range(len(x_values) - 1):
        for y_index in range(len(y_values) - 1):
            x0 = x_values[x_index]
            x1 = x_values[x_index + 1]
            y0 = y_values[y_index]
            y1 = y_values[y_index + 1]
            center = np.array([(x0 + x1) * 0.5, (y0 + y1) * 0.5], dtype=float)
            if _point_in_polygon_2d(center, vertices, tolerance):
                occupied.add((x0, x1, y0, y1))
    return occupied

def _point_in_polygon_2d(point: np.ndarray, vertices: np.ndarray, tolerance: float) -> bool:
    x_value = float(point[0])
    y_value = float(point[1])
    inside = False
    for index in range(len(vertices)):
        x0, y0 = vertices[index]
        x1, y1 = vertices[(index + 1) % len(vertices)]
        if abs(_cross2d(np.array([x_value - x0, y_value - y0]), np.array([x1 - x0, y1 - y0]))) <= tolerance:
            if min(x0, x1) - tolerance <= x_value <= max(x0, x1) + tolerance and min(y0, y1) - tolerance <= y_value <= max(y0, y1) + tolerance:
                return True
        intersects = ((y0 > y_value) != (y1 > y_value)) and (x_value < (x1 - x0) * (y_value - y0) / (y1 - y0 + 1e-30) + x0)
        if intersects:
            inside = not inside
    return inside

def _decompose_cells_into_max_rectangles(cells: set[tuple[float, float, float, float]]) -> list[tuple[float, float, float, float]]:
    remaining = set(cells)
    rectangles = []
    while remaining:
        seed = min(remaining, key=lambda cell: (cell[2], cell[0], -(cell[3] - cell[2]), -(cell[1] - cell[0])))
        x0, x1, y0, y1 = seed
        width_candidates = sorted({cell[1] for cell in remaining if abs(cell[0] - x0) <= 1e-12 and abs(cell[2] - y0) <= 1e-12})
        best_rectangle = seed
        for candidate_x1 in width_candidates:
            current_y1 = y1
            while True:
                candidate = (x0, candidate_x1, y0, current_y1)
                if not _rectangle_cells_present(candidate, remaining):
                    break
                best_rectangle = candidate
                next_row_y1 = _find_next_row_y1(candidate, remaining)
                if next_row_y1 is None:
                    break
                current_y1 = next_row_y1
        rectangles.append(best_rectangle)
        _remove_rectangle_cells(best_rectangle, remaining)
    return rectangles

def _rectangle_cells_present(rectangle, cells: set[tuple[float, float, float, float]]) -> bool:
    x0, x1, y0, y1 = rectangle
    column_edges = sorted({cell[0] for cell in cells if y0 <= cell[2] < y1 and x0 <= cell[0] < x1} | {x1})
    row_edges = sorted({cell[2] for cell in cells if x0 <= cell[0] < x1 and y0 <= cell[2] < y1} | {y1})
    for column_index in range(len(column_edges) - 1):
        for row_index in range(len(row_edges) - 1):
            candidate = (column_edges[column_index], column_edges[column_index + 1], row_edges[row_index], row_edges[row_index + 1])
            if candidate not in cells:
                return False
    return True

def _find_next_row_y1(rectangle, cells: set[tuple[float, float, float, float]]):
    x0, x1, _y0, y1 = rectangle
    next_y_candidates = sorted({cell[3] for cell in cells if abs(cell[2] - y1) <= 1e-12 and x0 <= cell[0] < x1})
    if not next_y_candidates:
        return None
    next_y1 = next_y_candidates[0]
    candidate = (x0, x1, y1, next_y1)
    if _rectangle_cells_present(candidate, cells):
        return next_y1
    return None

def _remove_rectangle_cells(rectangle, cells: set[tuple[float, float, float, float]]) -> None:
    x0, x1, y0, y1 = rectangle
    to_remove = {cell for cell in cells if x0 <= cell[0] < x1 and x0 < cell[1] <= x1 and y0 <= cell[2] < y1 and y0 < cell[3] <= y1}
    cells.difference_update(to_remove)

def _rectangle_polygon_from_cell_rectangle(rectangle) -> tuple[tuple[float, float], ...]:
    x0, x1, y0, y1 = rectangle
    return (
        (x0, y0),
        (x1, y0),
        (x1, y1),
        (x0, y1),
    )
