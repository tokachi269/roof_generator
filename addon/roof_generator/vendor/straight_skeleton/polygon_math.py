# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import itertools
from enum import Enum
from functools import partial
from typing import Any, Protocol

from .constants import NONCOLLINEARITY_EPSILON_DEGS, TIGHT_COLLINEARITY_EPSILON_DEGS
from .vector_math import Line2, Orientation, Ray2, Vector2


class PolygonMathTracerProtocol(Protocol):
    """Protocol to receive notifications of key polygon math operations, specially edge cases."""

    def on_compute_from_edges_are_opposite(self, vertex_info: VertexInfo):
        """Called when the edges that spawn a new vertex are parallel and face opposite directions (anti-parallel)."""
        ...

    def on_compute_from_edges_are_aligned(self, vertex_info: VertexInfo):
        """Called when the edges that spawn a new vertex are parallel and face the same direction (aligned)."""
        ...

    def on_lav_infinite_loop_detected(self, lav: LAV):
        """Called when we iterate a LAV with an infinite loop."""
        ...

    def on_degenerate_lav_detected(self, lav: LAV):
        """Called when a LAV is detected to be degenerate (all vertices are the same)."""
        ...


class NoopPolygonMathTracer(PolygonMathTracerProtocol):
    """Implementation of the PolygonMathTracerProtocol that does nothing on each notification."""

    def on_compute_from_edges_are_opposite(self, vertex_info: VertexInfo):
        pass

    def on_compute_from_edges_are_aligned(self, vertex_info: VertexInfo):
        pass

    def on_lav_infinite_loop_detected(self, lav: LAV):
        pass

    def on_degenerate_lav_detected(self, lav):
        pass


# Global tracer that can be replaced by the user to receive key events for debugging and logging.
GLOBAL_POLYGON_MATH_TRACER: PolygonMathTracerProtocol = NoopPolygonMathTracer()


def set_global_polygon_math_tracer(tracer: PolygonMathTracerProtocol):
    """Set a custom global tracer for polygon math operations."""
    global GLOBAL_POLYGON_MATH_TRACER
    GLOBAL_POLYGON_MATH_TRACER = tracer


class InsidePolygonCheckPolicy(Enum):
    """Policy to follow when we check if a vector is inside a LAV, specifically around parallel segments."""

    RELAXED = 0  # Checks will generally accept cases if any condition passes.
    STRICT = 1  # Checks will generally accept cases if all conditions pass.
    RAISE_ERROR = 2  # Checks will raise an error, failing execution, for parallel cases (mostly for debugging).


def is_vector_in_segment_polygon(
    prev_segment: Vector2,
    next_segment: Vector2,
    candidate_vector: Vector2,
    policy: InsidePolygonCheckPolicy = InsidePolygonCheckPolicy.RAISE_ERROR,
    collinearity_epsilon_degrees: float = TIGHT_COLLINEARITY_EPSILON_DEGS,
) -> bool:
    """Check if a candidate vector is inside the polygon that the two segments belong to. The polygon, by convention,
    is to the left of the segments. Note that here "polygon" may refer to the polygon defined by a LAV, not necessarily
    the initial polygon.

    Args:
        prev_segment: Segment that arrives to the vertex in the polygon we are checking.
        next_segment: Segment that leaves the vertex in the polygon we are checking.
        candidate_vector: Vector whose direction we want to check, and that is considered as starting on the same
            vertex as the segments.
        policy: Policy to follow when comparing against parallel segments. See InsidePolygonCheckPolicy.

    Raises:
        RuntimeError: If the policy is set to RAISE_ERROR and the segments are (parallel) aligned or opposite.
        ValueError: If the specified policy is not recognized.

    Returns:
        True if the candidate vector is inside the left polygon defined by the two given segments, False otherwise.
    """
    bis_vs_p_segment = Orientation.of_vec_with_respect_to(
        vec=candidate_vector, wrt=prev_segment, collinearity_epsilon_degrees=collinearity_epsilon_degrees
    )
    bis_vs_n_segment = Orientation.of_vec_with_respect_to(
        vec=candidate_vector, wrt=next_segment, collinearity_epsilon_degrees=collinearity_epsilon_degrees
    )
    segment_ori = Orientation.of_vec_with_respect_to(
        vec=next_segment, wrt=prev_segment, collinearity_epsilon_degrees=collinearity_epsilon_degrees
    )
    # TODO Need to review whether the inclusive checks here should allow opposites. Add unit-tests.
    if segment_ori.is_left_exclusive():
        # Convex angle
        # The polygon is to the left if bisector is Left-Left with respect to our segments.
        is_polygon_left = bis_vs_p_segment.is_left_inclusive() and bis_vs_n_segment.is_left_inclusive()
    elif segment_ori.is_right_exclusive():
        # Reflex angle
        # The polygon is to the left if the bisector is not Right-Right with respect to our segments.
        is_polygon_left = bis_vs_p_segment.is_left_inclusive() or bis_vs_n_segment.is_left_inclusive()
    elif segment_ori.is_aligned():
        # This is like the convex angle, however it is possible that the bisector is between our segments, failing
        # the Left-Left check. Pick which vector to check based on the policy.
        if policy == InsidePolygonCheckPolicy.RELAXED:
            # Relaxed, it is inside as long as it is with respect to the most open segment.
            is_polygon_left = bis_vs_p_segment.is_left_inclusive() or bis_vs_n_segment.is_left_inclusive()
        elif policy == InsidePolygonCheckPolicy.STRICT:
            # Strict, it is inside only if it is inside both segments.
            is_polygon_left = bis_vs_p_segment.is_left_inclusive() and bis_vs_n_segment.is_left_inclusive()
        elif policy == InsidePolygonCheckPolicy.RAISE_ERROR:
            raise RuntimeError("Parallel segments, can't determine if the bisector is inside the left-polygon.")
        else:
            raise ValueError(f"Unknown policy {policy}")
    elif segment_ori.is_opposite():
        if policy == InsidePolygonCheckPolicy.RELAXED:
            # Relaxed, it is inside as long as it is antiparallel to the previous edge (the one that goes into
            # the vertex), or parallel to the next edge (the one that goes out of the vertex).
            is_polygon_left = bis_vs_p_segment.is_opposite() or bis_vs_n_segment.is_aligned()
        elif policy == InsidePolygonCheckPolicy.STRICT:
            # Strict, it is inside as long as it is antiparallel to the previous edge (the one that goes into
            # the vertex), and parallel to the next edge (the one that goes out of the vertex).
            is_polygon_left = bis_vs_p_segment.is_opposite() and bis_vs_n_segment.is_aligned()
        elif policy == InsidePolygonCheckPolicy.RAISE_ERROR:
            raise RuntimeError("Antiparallel segments, can't determine if the bisector is inside the left-polygon.")
        else:
            raise ValueError(f"Unknown policy {policy}")
    return is_polygon_left


def is_point_inside_polygon_edges(edges: list[Edge], point2d: Vector2) -> bool:
    """Determine if a point is inside a polygon defined by its edges using the ray-casting algorithm.

    Note holes are purposely ignored, as they are not relevant for this check. This method returns true even if
    the point is inside a hole.

    Args:
        edges: List of edges that form the outside of the polygon. Holes are not relevant for this check.
        point2d: Point to check if it is inside the polygon.

    Returns:
        True if the point is inside the polygon exterior, defined by its edges, False otherwise.
    """
    x, y = point2d
    inside = False

    for edge in edges:
        (x1, y1), (x2, y2) = edge.start_vertex.position.coords, edge.end_vertex.position.coords

        # Check if the point is within the vertical range of the edge
        if min(y1, y2) < y <= max(y1, y2):
            # Calculate the intersection of the edge with the ray extending from the point to the right
            if x1 != x2:  # Avoid division by zero for vertical lines
                x_intersect = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            else:
                x_intersect = x1  # The edge is vertical

            # If the intersection is to the right of the point, toggle the 'inside' state
            if x <= x_intersect:
                inside = not inside

    return inside


class DegenerateLAVError(Exception):
    """Custom exception for degenerate LAVs (all points in the LAV are the same)."""

    pass


class VertexNotComputedError(Exception):
    """Custom exception when we try to access properties of a vertex that were not yet computed."""

    pass


class VertexInfo:
    """Extended information about a Vertex in a LAV."""

    __id_counter = itertools.count()

    @classmethod
    def reset_count(cls):
        cls.__id_counter = itertools.count()

    def __init__(self, position: Vector2, lav_ptr: LAV, split_dummy_vertex: VertexInfo | None = None):
        """Initializes a new VertexInfo at the given position, with a pointer to its containing LAV.

        Many of the attributes accessed through properties require computation, and are not available until the
        computation is executed. See `compute_from_edges`.

        Args:
            position: Position of the vertex.
            lav_ptr: Pointer to the LAV that contains this vertex.
            split_dummy_vertex: Optional dummy vertex that vertices created by split events may have. This is used to
                link arcs to the same vertex (the dummy vertex), even when the arcs reference one of the split vertices.
        """
        self._auto_id = next(self.__id_counter)

        self.position = position
        self.lav_ptr = lav_ptr
        self.processed = False
        self.split_dummy_vertex = split_dummy_vertex

        # Pointers to the original polygon edges.
        self.prev_orig_edge: Edge | None = None
        self.next_orig_edge: Edge | None = None
        # Linked list pointers.
        self.__next_vertex: VertexInfo | None = None
        self.__prev_vertex: VertexInfo | None = None

        # Private attributes (some need to be computed later).
        self.__computed: bool = False
        self.__bisector_direction: Vector2 | None = None
        self.__is_reflex: bool | None = None

        self._pending_split_events: list[Any] | None = None
        self._pending_split_events_computed = False

    def __hash__(self):
        """For comparison. Note that only the id is taken into account, so two vertex infos at the same location are
        considered different."""
        return hash(self._auto_id)

    def __repr__(self):
        return (
            f"VertexInfo(id={self._auto_id}"
            + f", position={self.position}"
            + f", lav={self.lav_ptr._auto_id}"
            + f", processed={self.processed}"
            + f", reflex={self.is_reflex if self.__computed else 'N/A'}"
            + f", [prev={self.prev_vertex._auto_id if self.__prev_vertex is not None else 'None'}"
            + f", next={self.next_vertex._auto_id if self.__next_vertex is not None else 'None'}]"
        )

    @property
    def next_vertex(self) -> VertexInfo:
        """Returns the next vertex in the LAV."""
        if self.__next_vertex is None:
            raise RuntimeError("next_vertex not set.")
        return self.__next_vertex

    @next_vertex.setter
    def next_vertex(self, value: VertexInfo):
        self.__next_vertex = value

    @property
    def prev_vertex(self) -> VertexInfo:
        """Returns the previous vertex in the LAV."""
        if self.__prev_vertex is None:
            raise RuntimeError("prev_vertex not set.")
        return self.__prev_vertex

    @prev_vertex.setter
    def prev_vertex(self, value: VertexInfo):
        self.__prev_vertex = value

    @property
    def pending_split_events(self) -> list[Any]:
        """Returns the pending split events for this vertex."""
        if not self._pending_split_events_computed:
            raise RuntimeError("Pending split events not computed.")
        assert self._pending_split_events is not None  # for mypy, since we set it when we compute it.
        return self._pending_split_events

    @pending_split_events.setter
    def pending_split_events(self, split_events: list[Any]):
        """Sets the pending split events for this vertex, flagging as computed."""
        if self._pending_split_events_computed:
            raise RuntimeError("Pending split events were already computed.")
        self._pending_split_events = split_events
        self._pending_split_events_computed = True

    @property
    def pending_split_events_computed(self) -> bool:
        """Returns whether the pending split events have been computed."""
        return self._pending_split_events_computed

    @property
    def is_reflex(self) -> bool:
        """Returns whether the vertex is reflex or not. The vertex info must be computed before accessing this property."""
        if not self.__computed:
            raise VertexNotComputedError()
        assert self.__is_reflex is not None  # for mypy, since we set it when we compute it.
        return self.__is_reflex

    # TODO I think `force_reflex` can be removed. See note in the caller.
    def force_reflex(self, value: bool):
        """This allows setting the reflex property after it has been auto-computed.

        Although not ideal, turns out to be necessary for edge events, which can accidentally detect reflex vertices
        when they are not. We should fix that underlying issue, but for now this is a workaround."""
        if not self.__computed:
            raise VertexNotComputedError()
        self.__is_reflex = value

    @property
    def bisector_direction(self) -> Vector2:
        """Returns the direction of the bisector of the vertex. The vertex info must be computed before accessing this property."""
        if not self.__computed:
            raise VertexNotComputedError()
        return self.__bisector_direction

    def bisector_ray(self):
        """Returns a Ray2 starting at the vertex and pointing in the same direction as the vertex's bisector."""
        return Ray2(self.position, self.bisector_direction)

    def get_prev_vertex_safe(self) -> VertexInfo:
        """Iterate our linked vertices backwards until we find one that is not overlapping with us.

        Raises:
            RuntimeError: If an infinite loop is detected.
            DegenerateLAVError: If all vertices are overlapping, and we can't find a safe previous vertex.

        Returns:
            The first vertex that is not overlapping with the vertex, found iterating backwards the linked list / LAV.
        """
        # Iterate vertices until we find one that is not overlapping with us (backward direction).
        visited = set()
        prev_ptr = self.prev_vertex
        visited.add(prev_ptr)
        while prev_ptr.position == self.position:
            prev_ptr = prev_ptr.prev_vertex
            # We might want to notify tracers if these happen.
            if prev_ptr in visited:
                raise RuntimeError("Infinite loop detected in `get_prev_vertex_safe`.")
            if prev_ptr == self:
                raise DegenerateLAVError("All vertices are overlapping, can't get a safe prev vertex.")
            visited.add(prev_ptr)
        return prev_ptr

    def get_next_vertex_safe(self) -> VertexInfo:
        """Iterate our linked vertices forward until we find one that is not overlapping with us.

        Raises:
            RuntimeError: If an infinite loop is detected.
            DegenerateLAVError: If all vertices are overlapping, and we can't find a safe next vertex.

        Returns:
            The first vertex that is not overlapping with the vertex, found iterating forward the linked list / LAV.
        """
        # Iterate vertices until we find one that is not overlapping with us (forward direction).
        visited = set()
        next_ptr = self.next_vertex
        visited.add(next_ptr)
        while next_ptr.position == self.position:
            next_ptr = next_ptr.next_vertex
            # We might want to notify tracers if these happen.
            if next_ptr in visited:
                raise RuntimeError("Infinite loop detected in `get_next_vertex_safe`.")
            if next_ptr == self:
                raise DegenerateLAVError("All vertices are overlapping, can't get a safe next vertex.")
            visited.add(next_ptr)
        return next_ptr

    def _is_self_bisector_inside_lav(self) -> bool:
        """Return whether our computed bisector is pointing towards the inside the LAV, comparing our previous
        and next safe sements (that is, the first ones whose other point does not overlap with this vertex).

        Returns:
            True if the bisector is pointing towards inside the LAV, False otherwise.
        """
        try:
            prev_segment = (self.position - self.get_prev_vertex_safe().position).normalized()
            next_segment = (self.get_next_vertex_safe().position - self.position).normalized()
        except DegenerateLAVError:
            return False  # LAV is a point, no bisector will be inside.

        return is_vector_in_segment_polygon(prev_segment, next_segment, candidate_vector=self.bisector_direction)

    def compute_from_edges(self) -> None:
        """Compute the bisector of the vertex and whether it is reflex, based on the edges that spawn it.

        Raises:
            RuntimeError: If the vertex's properties were already computed.
        """
        if self.__computed:
            raise RuntimeError("Vertex was already computed.")

        if self.prev_orig_edge is None or self.next_orig_edge is None:
            raise RuntimeError("Edges have not been set in the vertex.")

        in_edge = self.prev_orig_edge.direction
        out_edge = self.next_orig_edge.direction
        in_edge_inv = -in_edge

        # Figuring out the direction of the bisector from the creating edges is not as trivial as it seems. In
        # particular, there are edge cases around collinear edges, which can happen in different ways for original
        # vertices and non-original skeleton nodes.
        is_in_original_prev_edge = self.prev_orig_edge.has_endpoint(self)
        is_in_original_next_edge = self.next_orig_edge.has_endpoint(self)
        assert is_in_original_prev_edge == is_in_original_next_edge, "Vertices should belong to both or neither edge."
        is_original_vertex = is_in_original_prev_edge

        ori = Orientation.of_vec_with_respect_to(
            vec=out_edge, wrt=in_edge, collinearity_epsilon_degrees=TIGHT_COLLINEARITY_EPSILON_DEGS
        )
        if ori.is_opposite():
            # When they are opposite, we are unsure if the LAV is on the convex side or the reflex side. Attempt
            # to check very strictly against the LAV. If only one of the bisectors is inside, then that is the one we
            # want. If both are inside, we are still confused.
            bisector_pos = (in_edge_inv + out_edge).normalized()
            bisector_neg = -bisector_pos
            try:
                # Note that in/out segments are equal to the edges for the original vertices.
                in_segment = (self.position - self.get_prev_vertex_safe().position).normalized()
                out_segment = (self.get_next_vertex_safe().position - self.position).normalized()
            except DegenerateLAVError as e:
                # If the LAV is collapsed into a point, no bisector will be inside. This should not happen.
                GLOBAL_POLYGON_MATH_TRACER.on_degenerate_lav_detected(lav=self.lav_ptr)
                raise e
            is_in_pos = is_vector_in_segment_polygon(
                prev_segment=in_segment,
                next_segment=out_segment,
                candidate_vector=bisector_pos,
                collinearity_epsilon_degrees=NONCOLLINEARITY_EPSILON_DEGS,
            )
            is_in_neg = is_vector_in_segment_polygon(
                prev_segment=in_segment,
                next_segment=out_segment,
                candidate_vector=bisector_neg,
                collinearity_epsilon_degrees=NONCOLLINEARITY_EPSILON_DEGS,
            )
            if is_in_neg == is_in_pos:
                # See if the less relaxed version can tell them apart.
                is_in_pos = is_vector_in_segment_polygon(
                    prev_segment=in_segment,
                    next_segment=out_segment,
                    candidate_vector=bisector_pos,
                    collinearity_epsilon_degrees=TIGHT_COLLINEARITY_EPSILON_DEGS,
                )
                is_in_neg = is_vector_in_segment_polygon(
                    prev_segment=in_segment,
                    next_segment=out_segment,
                    candidate_vector=bisector_neg,
                    collinearity_epsilon_degrees=TIGHT_COLLINEARITY_EPSILON_DEGS,
                )
            if is_in_neg == is_in_pos:
                raise RuntimeError("Can't determine bisector direction for opposite edges.")

            if is_in_pos:
                bisector = bisector_pos
                is_reflex = False
            else:
                bisector = bisector_neg
                is_reflex = True
            GLOBAL_POLYGON_MATH_TRACER.on_compute_from_edges_are_opposite(vertex_info=self)
        elif ori.is_aligned():
            # If the two edges are pointing in the same direction, their desired bisector is perpendicular to the edges,
            # and towards their left (inwards wrt the polygon).
            bisector = Vector2(-in_edge.y, in_edge.x).normalized()
            is_reflex = False
            GLOBAL_POLYGON_MATH_TRACER.on_compute_from_edges_are_aligned(vertex_info=self)
        else:
            # If the point is part of the edges, we are in the vanilla case.
            if is_original_vertex:
                bisector = (in_edge_inv + out_edge).normalized()
                is_reflex = ori.is_right_exclusive()
                if is_reflex:
                    bisector = -bisector
            else:
                bisector = (in_edge_inv + out_edge).normalized()
                is_reflex = ori.is_right_exclusive()

        # Set final values.
        self.__is_reflex = is_reflex
        self.__bisector_direction = bisector.normalized()
        self.__computed = True


class Edge:
    """Information about an edge in the original polygon."""

    __id_counter = itertools.count()

    @classmethod
    def reset_count(cls):
        cls.__id_counter = itertools.count()

    def __init__(self, start_vertex: VertexInfo, end_vertex: VertexInfo, is_original_edge: bool = True):
        """Initializes a new Edge between two vertices. The edge is automatically set on the vertices, if this
        edge is an original edge. Direction of the edge is from start to end.

        Args:
            start_vertex: Start vertex of the edge.
            end_vertex: End vertex of the edge.
            is_original_edge: Whether this is an edge in the original polygon.
        """
        self._auto_id = next(self.__id_counter)

        self.start_vertex = start_vertex
        self.end_vertex = end_vertex
        self.direction = (end_vertex.position - start_vertex.position).normalized()

        # Automatically set this edge on the vertices.
        if is_original_edge:
            start_vertex.next_orig_edge = self
            end_vertex.prev_orig_edge = self

    def __repr__(self):
        return f"Edge(id={self._auto_id}, {self.start_vertex.position}, {self.end_vertex.position})"

    def has_endpoint(self, vertex: VertexInfo) -> bool:
        """Return whether the edge has the given vertex as one of its endpoints."""
        return vertex == self.start_vertex or vertex == self.end_vertex

    @property
    def start_p(self):
        """Return the start vertex's position."""
        return self.start_vertex.position

    @property
    def end_p(self):
        """Return the end vertex's position."""
        return self.end_vertex.position

    @property
    def center_p(self):
        """Return the center point of the edge."""
        return (self.start_p + self.end_p) / 2

    def distance_point_to_edge_line(self, point: Vector2, signed: bool = False) -> float:
        """Return the distance from the point to the infinite line holding this edge, optionally signed/unsigned.

        Args:
            point: Point to compute the distance to the edge.
            signed: Whether to return the signed distance or the absolute distance.

        Returns:
            The distance from the point to the infinite line holding this edge.
        """
        # Convert the edge to a line and then compute the distance.
        line = Line2(self.start_p, self.direction)
        d = line.signed_distance(point)
        return d if signed else abs(d)

    def is_point_in_edge_region(
        self,
        point: Vector2,
        *,
        allow_inclusive: bool = True,
        collinearity_epsilon_degrees: float = TIGHT_COLLINEARITY_EPSILON_DEGS,
    ) -> bool:
        """Return whether the given point is inside the region defined by this edge and the bisectors of its
        vertices. The region is to the left of the edge, and the bisectors are considered as rays starting at the
        vertices.

        Note on `allow_inclusive`: Conceptually the checks should be inclusive, however some skeletons may fail
        depending on the collinearity epsilon values if inclusivity is enabled (specifically with eps > 1 deg).

        Args:
            point: Point to check if it is inside the region defined by this edge and the bisectors of its vertices.
            allow_inclusive: Whether to consider points on the boundaries as inside the region.

        Returns:
            True if the point is inside the region, False otherwise
        """
        # Classify the point based on its location relative to the boundaries.
        start_p, start_bis = self.start_vertex.position, self.start_vertex.bisector_direction
        end_p, end_bis = self.end_vertex.position, self.end_vertex.bisector_direction

        left_check = (
            partial(Orientation.is_left_inclusive, allow_aligned=True, allow_opposite=False)
            if allow_inclusive
            else Orientation.is_left_exclusive
        )
        right_check = (
            partial(Orientation.is_right_inclusive, allow_aligned=True, allow_opposite=False)
            if allow_inclusive
            else Orientation.is_right_exclusive
        )

        # Special case for the start and end points, since otherwise we can't normalize their directions.
        if point == start_p or point == end_p:
            return allow_inclusive

        # Needs to be:
        # a) right or on top of the start bisector.
        start_ori = Orientation.of_vec_with_respect_to(
            vec=(point - start_p), wrt=start_bis, collinearity_epsilon_degrees=collinearity_epsilon_degrees
        )
        on_start_bis_right = right_check(start_ori)
        # b) left or on top of the edge.
        edge_ori = Orientation.of_vec_with_respect_to(
            vec=(point - start_p), wrt=self.direction, collinearity_epsilon_degrees=collinearity_epsilon_degrees
        )
        on_edge_left = left_check(edge_ori)
        # c) left or on top of the end bisector.
        end_ori = Orientation.of_vec_with_respect_to(
            vec=(point - end_p), wrt=end_bis, collinearity_epsilon_degrees=collinearity_epsilon_degrees
        )
        on_end_bis_left = left_check(end_ori)

        # The point is inside the region if it's on the correct side of all three boundaries.
        return on_start_bis_right and on_edge_left and on_end_bis_left


class LAV:
    """List of active vertices."""

    # Automatic counter to assign unique ids to each LAV.
    __id_counter = itertools.count()

    @classmethod
    def reset_count(cls):
        cls.__id_counter = itertools.count()

    def __init__(self, head: VertexInfo | None = None):
        """Initialize the LAV with an optional head vertex.

        Args:
            head: Initial vertex of the LAV (if any).
        """
        self._auto_id = next(self.__id_counter)

        self.head = head

    def __hash__(self) -> int:
        """For storage in the set of LAVs. Note that only the id is taken into account."""
        return hash(self._auto_id)

    def __eq__(self, other: object) -> bool:
        """Compares two LAVS, based exclusively on their unique ids, regardless of other values."""
        if not isinstance(other, LAV):
            return NotImplemented
        return self._auto_id == other._auto_id

    def __iter__(self):
        """Iterate over the vertices in the LAV, checking for (infinite) loops."""
        if self.head is None:
            return
        visited = set()  # Should not be needed, but the code is setup for tracing unexpected cases.
        current = self.head

        # We do unbounded iteration since we check for loops. Otherwise we might want to set up a limit.
        while True:
            yield current
            visited.add(current)
            current = current.next_vertex
            if current == self.head:
                break
            if current in visited:
                GLOBAL_POLYGON_MATH_TRACER.on_lav_infinite_loop_detected(self)
                raise RuntimeError(f"Infinite loop in LAV. Visited {len(visited)} vertices.")

    def append_vertex_at(self, point: Vector2) -> None:
        """Creates a new vertex info and adds it to the tail of the LAV, at the specified point.

        Args:
            point: 2D point to add a vertex at. The other vertex properties are not yet computed, since they require
                additional information.
        """
        new_vertex = VertexInfo(position=point, lav_ptr=self)
        if self.head is None:
            self.head = new_vertex
            self.head.next_vertex = self.head
            self.head.prev_vertex = self.head
        else:
            last_vertex = self.head.prev_vertex
            # Insert the new vertex between the head and the last
            self.head.prev_vertex = new_vertex
            last_vertex.next_vertex = new_vertex
            new_vertex.prev_vertex = last_vertex
            new_vertex.next_vertex = self.head
