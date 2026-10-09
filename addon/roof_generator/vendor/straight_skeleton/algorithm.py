# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import heapq
import itertools
import math
from enum import Enum, auto
from typing import Generic, Iterator, Protocol, TypeAlias, TypeVar, cast

from .constants import DISTANCE_EPSILON, NONCOLLINEARITY_EPSILON_DEGS, TIME_EPSILON
from .polygon_math import LAV, DegenerateLAVError, Edge, VertexInfo, is_point_inside_polygon_edges
from .skeleton import Skeleton
from .vector_math import Line2, Orientation, Ray2, Vector2


class AlgorithmTracerProtocol(Protocol):
    """Protocol to receive notifications from key algorithm steps and edge cases."""

    def on_reflex_vertex_found_after_edge_event(self, vertex: VertexInfo):
        """Called when we decide a vertex is reflex after an edge event, which should not happen and causes issues."""
        ...

    def on_failed_to_find_opposite_edge(self, event_info: SplitEventInfo):
        """Called when we fail to find the opposite edge for a split event, which sometimes is expected if the
        opposite edge has collapsed due to other events."""
        ...

    def on_step_begin(self, step: int, time: float, algorithm: StraightSkeletonAlgorithm):
        """Called at the beginning of each iteration of the algorithm's main loop."""
        ...

    def on_event_popped(self, step: int, time: float, event_info: EventInfo, algorithm: StraightSkeletonAlgorithm):
        """Called when an event is popped from the priority queue and is about to be processed."""
        ...

    def on_vertex_attempting_event_requeue(self, vertex: VertexInfo):
        """Called when a vertex that failed to process an event is attempting to requeue a new event."""
        ...

    def on_vertex_became_its_opposite_edge(self, event_info: SplitEventInfo):
        """Called when a vertex becomes its own opposite edge, which should not happen and can cause issues."""
        ...

    def on_algorithm_end(self, algorithm: StraightSkeletonAlgorithm):
        """Called when the algorithm finishes processing all events and the skeleton is complete."""
        ...

    def on_algorith_raised_exception(self, algorithm: StraightSkeletonAlgorithm, exception: Exception):
        """Called when the algorithm raises an exception, which should not happen and signals a bug."""
        ...

    def on_debug_hit(self, algorithm: StraightSkeletonAlgorithm):
        """General hook for debugging during edge cases."""
        ...


class NoopAlgorithmTracer(AlgorithmTracerProtocol):
    """Implementation of the AlgorithmTracerProtocol that does nothing on each notification."""

    def on_reflex_vertex_found_after_edge_event(self, vertex: VertexInfo):
        pass

    def on_failed_to_find_opposite_edge(self, event_info: SplitEventInfo):
        pass

    def on_step_begin(self, step: int, time: float, algorithm: StraightSkeletonAlgorithm):
        pass

    def on_event_popped(self, step: int, time: float, event_info: EventInfo, algorithm: StraightSkeletonAlgorithm):
        pass

    def on_vertex_attempting_event_requeue(self, vertex: VertexInfo):
        pass

    def on_vertex_became_its_opposite_edge(self, event_info: SplitEventInfo):
        pass

    def on_algorithm_end(self, algorithm: StraightSkeletonAlgorithm):
        pass

    def on_algorith_raised_exception(self, algorithm: StraightSkeletonAlgorithm, exception: Exception):
        pass

    def on_debug_hit(self, algorithm: StraightSkeletonAlgorithm):
        pass


# Global tracer that can be replaced by the user to receive key events for debugging and logging.
GLOBAL_ALGORITHM_TRACER: AlgorithmTracerProtocol = NoopAlgorithmTracer()


def set_global_algorithm_tracer(tracer: AlgorithmTracerProtocol):
    """Set a custom global algorithm tracer for algorithm notifications."""
    global GLOBAL_ALGORITHM_TRACER
    GLOBAL_ALGORITHM_TRACER = tracer


T = TypeVar("T")


class PriorityQueue(Generic[T]):
    """Priority queue implementation using a heap for efficient insertion and removal of items with priorities."""

    def __init__(self):
        """Initialize a new empty Priority Queue."""
        self._data = []

    def __len__(self) -> int:
        """Return the number of items in the priority queue."""
        return len(self._data)

    def __iter__(self) -> Iterator[tuple[float, T]]:
        """Iterate over the elements in priority order without modifying the queue, using a sorted copy."""
        return iter(sorted(self._data))

    def put(self, priority: float, item: T) -> None:
        """Insert the given item in the queue with the given priority.

        Args:
            priority: The priority of the item. Lower values are better priorities.
            item: The item to insert in the queue.
        """
        heapq.heappush(self._data, (priority, item))

    def get(self) -> tuple[float, T]:
        """Remove and return the item with the lowest(=best) priority from the queue. Raises IndexError if empty."""
        return heapq.heappop(self._data)

    def peek(self) -> tuple[float, T]:
        """Return the item with the lowest(=best) priority without removing it. Raises IndexError if empty."""
        if len(self._data) == 0:
            raise IndexError("Attempted to peek from empty priority queue.")
        return self._data[0]

    def empty(self) -> bool:
        """Return True if the priority queue is empty, False otherwise."""
        return len(self._data) == 0


class EventInfo:
    """Information about an 'event' in the context of edge wavefront events."""

    class EventType(Enum):
        EDGE = auto()  # An edge collapses.
        SPLIT = auto()  # A reflex vertex splits an edge.

    __id_counter = itertools.count()

    @classmethod
    def reset_count(cls):
        cls.__id_counter = itertools.count()

    def __init__(self, event_type: EventType, position: Vector2, distance: float):
        """Initialize the event with the given type, position and distance. A new unique id is automatically assigned
        to the event.

        Args:
            event_type: Type of event.
            position: Point where the event happens (generally a collision point between wavefronts).
            distance: Distance to the vertex that detected the event.
        """
        self._auto_id = next(self.__id_counter)

        self.event_type = event_type
        self.position = position
        self.distance = distance

    def __lt__(self, other: EventInfo):
        """Compare events based on their distance first. If the distance is the same (within epsilon), compare the auto
        id of the events, thus prioritizing the event that was detected first."""

        if not isinstance(other, EventInfo):
            return NotImplemented

        # TODO: In older versions of the algorithm, before event requeing on event failure, it was necessary to sort by
        # distance here if the priorities were tied. It seems that it now causes issues, and that event detection time
        # (equal to auto_id) is preferred in order to break ties. This however is brittle, and requires better
        # decision making when events happen at the same priority.
        # if abs(self.distance - other.distance) < TIME_EPSILON:
        #     return self._auto_id < other._auto_id
        # else:
        #     return self.distance < other.distance
        return self._auto_id < other._auto_id

    @property
    def is_edge_event(self):
        return self.event_type == self.EventType.EDGE

    @property
    def is_split_event(self):
        return self.event_type == self.EventType.SPLIT


class EdgeEventInfo(EventInfo):
    """Information about an edge event, where two bisectors intersect to collapse an edge."""

    def __init__(self, position: Vector2, distance: float, v_a: VertexInfo, v_b: VertexInfo):
        """Initialize the edge event with the given intersection position, the distance to the vertex that detected the
        event, and the two vertices whose bisectors cause the intersection, and therefore collapse of edge."""
        super().__init__(event_type=self.EventType.EDGE, position=position, distance=distance)
        self.v_a = v_a
        self.v_b = v_b

    def __repr__(self):
        return f"EdgeEventInfo({self._auto_id}, d={self.distance}, pos={self.position}, v_a={self.v_a}, v_b={self.v_b})"


class SplitEventInfo(EventInfo):
    """Information about a split event, where a reflex vertex splits an edge."""

    def __init__(self, position: Vector2, distance: float, v: VertexInfo, opposite_edge: Edge):
        """Initialize the split event with the given split position, the distance to the vertex causing the split, such
        vertex, and the original edge that will be split."""
        super().__init__(event_type=self.EventType.SPLIT, position=position, distance=distance)
        self.v = v
        self.opposite_edge = opposite_edge

    def __repr__(self):
        return f"SplitEventInfo({self._auto_id}, d={self.distance}, pos={self.position}, v={self.v}, edge={self.opposite_edge})"


# Type definitions.
EventQueue: TypeAlias = PriorityQueue[EventInfo]
SLAV: TypeAlias = set[LAV]
PointList: TypeAlias = list[tuple[float, float]]


class StraightSkeletonAlgorithm:
    """Encapsulates the straight skeleton computation algorithm itself."""

    def __init__(self, event_time_decimals: int | None = 6):
        """Initialize the algorithm with the given number of decimal places for event priorities.

        Args:
            event_time_decimals: The number of decimal places to consider to round event priorities and distances. If
                None, full precision is used. If set, the priorities and the distance to vertice will be rounded to the
                given number of decimals before they are compared. Note that if the number of decimals is less than the
                time comparison epsilon, rounding can cause issues, since rounding can pull close times apart more than
                that epsilon (eg: if decimals is 1, two close events 0.47 and 0.51 would now be 0.1 apart, which is much
                greater than the original 0.04 difference). This value should probably be >= decimals(TIME_EPSILON) + 1.
        """
        self.event_priority_decimals = event_time_decimals
        self.original_edges: list[Edge] = []
        self.skeleton: Skeleton = Skeleton(original_edges=[])
        self.slav = SLAV()

    def _round(self, value: float | None) -> float | None:
        """Round and return the given value to the number of decimals set for the algorithm."""
        if value is None:
            return None
        return round(value, self.event_priority_decimals) if self.event_priority_decimals is not None else value

    def _compute_closest_edge_event(self, vi: VertexInfo) -> tuple[float, EdgeEventInfo] | tuple[None, None]:
        """Computes the edge event which is closest to the given vertex, if any. Edge events happen when the bisector
        of the given vertex and the bisector of one of its neighbors intersect, collapsing the edge between them.

        Args:
            vi: The vertex for which to compute the nearest edge event.

        Returns:
            A tuple with the priority of the event and the event information, if an event is found. If no event is
            found, the tuple (None, None) is returned. The priority is the distance from the intersection point to the
            vanishing edge's holding line.
        """
        # Compute the intersection of the current bisector with the prev and next bisectors.
        cur_bisector = vi.bisector_ray()
        prev_bisector = vi.prev_vertex.bisector_ray()
        next_bisector = vi.next_vertex.bisector_ray()
        inter_prev = cur_bisector.intersection_with_ray(prev_bisector)
        inter_next = cur_bisector.intersection_with_ray(next_bisector)
        # Check if both intersections are None.
        if inter_prev is None and inter_next is None:
            return None, None
        # Take vars from the closer intersection.
        if inter_next is None:
            loc_i, va, vb = inter_prev, vi.prev_vertex, vi
        elif inter_prev is None:
            loc_i, va, vb = inter_next, vi, vi.next_vertex
        else:
            len_prev = (inter_prev - vi.position).length()
            len_next = (inter_next - vi.position).length()
            # If they are the same either should be fine.
            loc_i, va, vb = (
                (inter_prev, vi.prev_vertex, vi) if len_prev < len_next else (inter_next, vi, vi.next_vertex)
            )

        # Pick the edge (should be either next(a) or prev(b)).
        if va.next_orig_edge != vb.prev_orig_edge:
            raise RuntimeError("Unexpected condition: next_edge(a) != prev_edge(b)")
        edge_i = va.next_orig_edge

        # Compute queue priority and create the event.
        priority = edge_i.distance_point_to_edge_line(point=loc_i)
        priority = self._round(value=priority)
        distance = (loc_i - vi.position).length()
        distance = self._round(value=distance)
        event_info = EdgeEventInfo(position=loc_i, distance=distance, v_a=va, v_b=vb)
        return priority, event_info

    def _compute_split_events(self, vi: VertexInfo) -> None:
        """Compute the split events for a given vertex, and cache them in the vertex. Split events happen when a reflex
        vertex splits an opposing edge, potentially splitting the polygon into separate subpolygons.

        Args:
            vi: The vertex for which to compute the nearest split event.

        Raises:
            RuntimeError: In case of unexpected computations/conditions (might signal a bug).
        """
        if not vi.is_reflex:
            vi.pending_split_events = []
            return

        # Grab the segments for the vertex that we are going to operate on.
        try:
            prev_segment = (vi.position - vi.get_prev_vertex_safe().position).normalized()
            next_segment = (vi.get_next_vertex_safe().position - vi.position).normalized()
        except DegenerateLAVError:
            # LAV is a point, will not attempt to find split event.
            vi.pending_split_events = []
            return

        found_split_events = []

        # Note the order is important since events with same time will be ordered according to detection time.
        v_bisector_ray = vi.bisector_ray()
        for edge in self.original_edges:
            # Skip the edges for the vertex itself, they can't be the opposite edge.
            if edge.has_endpoint(vi):
                continue
            edge_line = Line2(point=edge.start_p, direction=edge.direction)

            # Check the intersection between the vertex's bisector and the line the edge lies on. If there is no
            # intersection, the edge is "behind" the vertex.
            inter_bisector_ei_line = edge_line.intersection_with_ray(ray=v_bisector_ray)
            if inter_bisector_ei_line is None:
                continue

            # Check the vertex's segments (as ending on it).
            for segment in [prev_segment, -next_segment]:
                # If the segment is collinear to the tested edge, skip it.
                if Orientation.of_vec_with_respect_to(vec=segment, wrt=edge.direction).is_collinear():
                    continue

                # Compute the "axis of the angle" between the segment and the edge line, choosing the direction of the
                # edge given the orientation of the axis with respect to the vertex's bisector.
                #   1. Compute the intersection point between the edge line and the segment line.
                #   2. Compute the axis of the angle by selecting the edge direction according to the orientation.
                #   3. Compute Bi as the intersection between the axis and the vertex's own bisector.
                segment_line = Line2(point=vi.position, direction=segment)

                # 1. Compute the intersection point between the edge line and the segment line.
                int_on_edge = edge_line.intersection_with_line(segment_line)
                if int_on_edge is None:
                    raise RuntimeError("Intersection expected since the lines are not parallel.")

                if vi.position == int_on_edge:
                    # The intersection is the vertex itself, so the vertex is part of the edge line.
                    # I think we can break instead of continue, since the other segment will not be valid either, but
                    # would need to verify that theory.
                    continue

                # 2. Compute the axis of the angle by selecting the edge orientation according to where the intersection
                # point lies with respect to the vertex's bisector.
                int_to_v_dir = (vi.position - int_on_edge).normalized()
                orientation = Orientation.of_vec_with_respect_to(
                    vec=int_to_v_dir,
                    wrt=v_bisector_ray.direction,
                    collinearity_epsilon_degrees=NONCOLLINEARITY_EPSILON_DEGS,
                    # collinearity_epsilon_degrees=TIGHT_COLLINEARITY_EPSILON_DEGS, See note below in `Issue: Collinear`
                )

                # Special consideration for collinear cases.
                if not orientation.is_collinear():
                    # If the incoming vector is to the right of the bisector, we invert the edge, since the intersection
                    # point is to the left of the vertex with respect to its bisector.
                    edge_dir = -edge.direction if orientation.is_right_exclusive() else edge.direction
                    int_bisector = (edge_dir + int_to_v_dir).normalized()

                    # 3. Compute Bi as the intersection between the axis and the vertex's own bisector.
                    int_b = v_bisector_ray.intersection_with_ray(Ray2(int_on_edge, int_bisector))
                    if int_b is None:
                        # There is no intersection, there will be no candidate point.
                        break
                else:
                    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                    # Issue: Collinear. There is a substantial problem here. The point we are computing is at an
                    # arbitrary location, since the event wants to happen almost on top of the edge itself. The
                    # correction that we do may, when events are processed, land very close to another skeleton node,
                    # while having a slightly different time, since they can come from different edges. During skeleton
                    # verification, this can result in nodes being at the same location, while having too different
                    # times, which is not correct (and currently fires an exception). To solve the issue we could:
                    # 0) Only provide one point, and crash due to the precision issue.
                    # a) Set `collinearity_epsilon_degrees` to NONCOLLINEARITY_EPSILON_DEGS above, so that we truly do
                    #   not fall here ever and trust precision to do its job.
                    # b) Flag in the event that the point is arbitrary, and that we are open to moving it.
                    # c) Create more than one event with different locations, flagging them as linked, and letting
                    #   one and only one contribute to the skeleton.
                    # ... others?
                    # Although I think (c) is the most correct, I need time to implement it and test it, so we will go
                    # with (a) for now. (b) seems wrong, since moving the point essentially causes different times,
                    # which could have impacted the skeleton construction up to that point.
                    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                    # The code below is for (0), which will currently not fire due to (a) being set.
                    # If the the vertex's bisector and its segment are almost parallel, Bi will be almost the same
                    # as the intersection point on the edge. However, the split point should not be on the edge, since
                    # that would be a degenerate case, so we need to find the closest point to the edge where Bi could
                    # be.
                    # In order to find where Bi could be, we know that its distance to the line holding the edge will be
                    # its priority, and that needs to be > TIME_EPSILON.
                    # MIN_DIST_B_TO_EDGE should be enough that the point is not collinear with respect to the edge, that
                    # depends on where the point is with respect to start_p, and the collinearity epsilon used in the
                    # region check `is_point_in_edge_region` below.
                    region_collinearity_eps = NONCOLLINEARITY_EPSILON_DEGS
                    min_degrees = region_collinearity_eps + 1e-5
                    dist_to_start_p = (int_on_edge - edge.start_p).length()
                    min_dist_b_to_edge = max(
                        math.sin(math.radians(min_degrees)) * dist_to_start_p, 2 * DISTANCE_EPSILON
                    )
                    # Compute such point.
                    desired_dist_along_v, desired_point = edge_line.find_point_with_min_distance_along_vector(
                        point=int_on_edge, vector=int_to_v_dir, min_distance=min_dist_b_to_edge
                    )
                    # But at the same time, we can't be past the vertex itself.
                    max_dist_int_towards_v = (vi.position - int_on_edge).length() - TIME_EPSILON

                    if desired_dist_along_v > max_dist_int_towards_v:
                        # If we can't find a point along the vector far enough from the edge but not past the vertex,
                        # we can't handle the split event that should go between the edge and the vertex.
                        raise RuntimeError("Reflex vertex too close to opposite edge without being part of the edge.")

                    # If we get here, we found a point.
                    int_b = desired_point

                # Now check whether Bi is inside the region defined by the edge and its bisectors.
                in_region = edge.is_point_in_edge_region(
                    point=int_b, collinearity_epsilon_degrees=NONCOLLINEARITY_EPSILON_DEGS
                )
                if not in_region:
                    # The candidate point is not in the region, this edge is not the opposite edge.
                    break

                # The point is a candidate event, add it the list of found events.
                dist_to_v = (int_b - vi.position).length()
                dist_to_v = self._round(value=dist_to_v)

                # Record the events.
                e_priority = edge.distance_point_to_edge_line(point=int_b)
                e_priority = self._round(value=e_priority)
                e_event_info = SplitEventInfo(position=int_b, distance=dist_to_v, v=vi, opposite_edge=edge)
                found_split_events.append((e_priority, e_event_info))

                # In any case, no need to check the second segment if the first one was not parallel, since B has the
                # same coordinates for both segments.
                break

        # Sort the split events by the distance to the vertex.
        found_split_events.sort(key=lambda x: x[1].distance)

        # Cache all split events in the vertex.
        vi.pending_split_events = found_split_events

    def _attempt_requeue_vertex_events(self, vi: VertexInfo) -> None:
        """Attempts to queue a new vertex event for the given vertex, which must be not yet processed.

        This is a modification to the original algorithm, which would only consider the closest event. When events fail
        (because part the other vertex has been processed or their opposite edge has collapsed), the unprocessed vetex
        can be left dangling. Those vertices have now a second chance of computing their next event. In order to do so,
        we compute the newest edge event possible, and check it against the next split event cached (if any).

        Args:
            vi: Vertex for which to attempt to queue a new event, since their intended event failed.

        Raises:
            RuntimeError: If the vertex is already processed.
        """
        if vi.processed:
            raise RuntimeError("Processed vertices don't get second chances.")

        # Notify that we are doing this to the tracer.
        GLOBAL_ALGORITHM_TRACER.on_vertex_attempting_event_requeue(vertex=vi)

        # Simply call queue again, since its implementation supports re-queueing events.
        self._queue_vertex_events(vi=vi)

    def _queue_vertex_events(self, vi: VertexInfo) -> None:
        """Compute the closest edge and all split events for the given vertex, and queue them with the appropriate
        priority, storing the cache of split events for later use if needed. If the cache was already computed, it will
        not be recomputed on subsequent calls.

        Args:
            vi: Vertex for which to compute the closest events.
        """
        # If already processed, this should not even be attempted.
        if vi.processed:
            raise RuntimeError("Processed vertices should not queue more events.")

        # Note the order of detection is important since events with same time will be ordered according to detection
        # time, as we compare their auto ids.

        # Check whether we should compute the split events now or they are already cached.
        if not vi.pending_split_events_computed:
            self._compute_split_events(vi=vi)

        # Always check the first split event against the edge event.
        if vi.pending_split_events:
            split_prio, split_event = vi.pending_split_events[0]
            split_dist = split_event.distance
        else:
            split_prio, split_event, split_dist = None, None, math.inf
        pop_split_event = False

        # Compute closest edge event.
        edge_prio, edge_event = self._compute_closest_edge_event(vi=vi)
        edge_dist = edge_event.distance if edge_event is not None else math.inf

        # Queue the closest one only.
        if split_dist < edge_dist:
            # Queue split event.
            assert split_prio is not None and split_event is not None  # for mypy
            self.queue.put(priority=split_prio, item=split_event)
            pop_split_event = True
        elif edge_dist < split_dist:
            # Queue edge event.
            assert edge_prio is not None and edge_event is not None  # for mypy
            self.queue.put(priority=edge_prio, item=edge_event)
        elif edge_event is not None:  # the distances are the same.
            # We can put both in the queue. Processing events at the same time is not a problem: we will process them
            # based on event comparison operator, and vertices that are already processed will be skipped.
            assert split_prio is not None and split_event is not None  # for mypy
            assert edge_prio is not None and edge_event is not None  # for mypy
            self.queue.put(split_prio, split_event)
            self.queue.put(edge_prio, edge_event)
            pop_split_event = True

        if pop_split_event:
            vi.pending_split_events.pop(0)

    def _initialize_from(self, exterior: PointList, holes: list[PointList]) -> None:
        """Initialize the algorithm's variables to compute the skeleton of a polygon defined by the given exterior
        and holes.

        Args:
            exterior: List of points defining the exterior of the polygon in COUNTER-CLOCKWISE orientation.
            holes: List of holes, each defined by a list of points in CLOCKWISE orientation.
        """
        self.original_edges = []
        self.slav = SLAV()
        self.queue = EventQueue()

        # Generate one LAV with the exterior vertices.
        first_lav = LAV()
        for v in exterior:
            # Skip last vertex for a closed polygon.
            p = Vector2(v[0], v[1])
            if first_lav.head is None or p != first_lav.head.position:
                first_lav.append_vertex_at(p)
        self.slav.add(first_lav)

        # Add holes (each as one lav).
        for hole in holes:
            hole_lav = LAV()
            for v in hole:
                p = Vector2(v[0], v[1])
                if hole_lav.head is None or p != hole_lav.head.position:
                    hole_lav.append_vertex_at(p)
            self.slav.add(hole_lav)

        # Build original edges from both exterior and holes.
        for lav in self.slav:
            for vi in lav:
                # Note the edge links itself to the vertices.
                self.original_edges.append(Edge(start_vertex=vi, end_vertex=vi.next_vertex))

        # Now we can create the skeleton instance, because we have computed the original edges.
        self.skeleton = Skeleton(original_edges=self.original_edges)

        # Compute each vertex info now that we have the edges.
        for lav in self.slav:
            for vi in lav:
                # Verify we set up the edges properly.
                assert vi.prev_orig_edge.end_vertex == vi, f"Vertex {vi} is not the end of its previous edge."
                assert vi.next_orig_edge.start_vertex == vi, f"Vertex {vi} is not the start of its next edge."
                # Compute bisector direction and reflexivity from the edges.
                vi.compute_from_edges()

        # Compute the initial set of events (edge and split) for each vertex in each lav.
        for lav in self.slav:
            for vi in lav:
                self._queue_vertex_events(vi=vi)

    def _process_edge_event(self, event_info: EdgeEventInfo, current_time: float) -> None:
        """Process an edge event, potentially adding arcs to the skeleton, and queueing new events if needed.

        Args:
            event_info: Event information.
            current_time: Current time.

        Raises:
            RuntimeError: If unexpected conditions are met (might signal a bug).
        """
        # (edge_event 2.b) If Va and Vb are processed, continue to (2).
        if event_info.v_a.processed or event_info.v_b.processed:
            if not event_info.v_a.processed:
                # v_a was not processed, but it's edge event vanished, give it a second chance for events.
                self._attempt_requeue_vertex_events(vi=event_info.v_a)

            if not event_info.v_b.processed:
                # v_b was not processed, but it's edge event vanished, give it a second chance for events.
                self._attempt_requeue_vertex_events(vi=event_info.v_b)

            # No further processing
            return

        # (edge_event 2.c) If prev(prev(Va)) == Vb (peak of the roof).
        if event_info.v_a.prev_vertex.prev_vertex == event_info.v_b:
            # Add three skeleton arcs [VaI, VbI, VcI], with Vc == prev(Va) = next(Vb), and continue to (2).
            if event_info.v_a.prev_vertex != event_info.v_b.next_vertex:
                raise RuntimeError("prev(prev(Va)) == Vb, but prev(Va) != next(Vb)")
            # Note we use a dummy here so that the skeleton can optimize finding its corresponding skeleton vertex.
            dummy_vertex = VertexInfo(event_info.position, lav_ptr=LAV())
            v_c = event_info.v_a.prev_vertex
            self.skeleton.add_arc(vertex_1=event_info.v_a, vertex_2=dummy_vertex, at_time=current_time)
            self.skeleton.add_arc(vertex_1=event_info.v_b, vertex_2=dummy_vertex, at_time=current_time)
            self.skeleton.add_arc(vertex_1=v_c, vertex_2=dummy_vertex, at_time=current_time)
            # Mark the three vertices as processed (although I think this is the end of the lav events).
            event_info.v_a.processed = True
            event_info.v_b.processed = True
            v_c.processed = True
            dummy_vertex.processed = True  # Also the dummy. Its lav is never part of the slav anyway.
            # We should remove this lav from the slav so the nodes are no longer searched for.
            self.slav.remove(event_info.v_a.lav_ptr)
            return

        # Implementation note: we do 2.e.2 before 2.d because we use the vertex's id as skeleton vertex id, so we need
        # to create the vertex before adding the arcs.
        # (edge_event 2.e.2) Create a new vertex at I.
        event_lav = event_info.v_a.lav_ptr
        new_vertex = VertexInfo(event_info.position, lav_ptr=event_lav)

        # (edge_event 2.d) Output two skeleton arcs [VaI, VbI].
        self.skeleton.add_arc(vertex_1=event_info.v_a, vertex_2=new_vertex, at_time=current_time)
        self.skeleton.add_arc(vertex_1=event_info.v_b, vertex_2=new_vertex, at_time=current_time)

        # (edge_event 2.e) Modify the LAV.
        # (edge_event 2.e.1) Mark Va and Vb as processed.
        event_info.v_a.processed = True
        event_info.v_b.processed = True
        # # (edge_event 2.e.2) Create a new vertex at I.
        # Done already (see note above).
        # event_lav = event_info.v_a.lav_ptr
        # new_vertex = VertexInfo(event_info.position, lav_ptr=event_lav)
        # (edge_event 2.e.3) Insert the new vertex into LAV, instead of Va and Vb.
        new_vertex.prev_vertex = event_info.v_a.prev_vertex
        new_vertex.next_vertex = event_info.v_b.next_vertex
        new_vertex.prev_vertex.next_vertex = new_vertex
        new_vertex.next_vertex.prev_vertex = new_vertex
        if event_lav.head == event_info.v_a or event_lav.head == event_info.v_b:
            event_lav.head = new_vertex
        # (edge_event 2.e.4) Link the appropriate edges to the new vertex.
        new_vertex.prev_orig_edge = event_info.v_a.prev_orig_edge
        new_vertex.next_orig_edge = event_info.v_b.next_orig_edge

        # - - - - - - - - - - - - - - - -
        # (edge_event 2.f) Compute V's events.
        # - - - - - - - - - - - - - - - -
        # (edge_event 2.f.1) Compute the new vertex's bisector.
        new_vertex.compute_from_edges()

        # TODO: This can still happen, but I believe it is correct to have them. I need to create a custom test to
        # verify that it is in fact required for them to be identified as reflex, so they can create split events even
        # if they are not original vertices. The test would involve two reflex vertices that collide, creating a
        # new vertex that is also reflex. Need to make sure that that reflex vertex should split the edge in front
        # of it. If so, then forcing that vertex to being non-reflex will be wrong.
        if new_vertex.is_reflex:
            new_vertex.force_reflex(value=False)
            GLOBAL_ALGORITHM_TRACER.on_reflex_vertex_found_after_edge_event(vertex=new_vertex)

        # (edge_event 2.f.2) Compute the intersections of the new bisector with the neighbor bisectors.
        # (edge_event 2.f.3) Store the nearer intersection point into the priority queue (if exists).
        # Implementation note: we would allow here split events if the vertex is reflex.
        self._queue_vertex_events(vi=new_vertex)

    def _process_split_event(self, event_info: SplitEventInfo, current_time: float) -> None:
        """Process a split event, potentially adding an arc to the skeleton, and queueing new events if needed.

        Args:
            event_info: Event information.
            current_time: Current time.

        Raises:
            RuntimeError: In case of unexpected conditions (might signal a bug).
        """
        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # (split_event 2.b) if the intersection point points to already processed vertices continue on step 2.
        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        if event_info.v.processed:
            return

        # (split_event 2.c) ... (continue)
        # (split_event 2.d) output one arc Vertex-Intersection of the straight skeleton.
        # Implementation note: This is a modification wrt to original algorithm, do not do it now since the split
        # event may fail due to the opposite edge having collapsed. In that case, we do not want to add the arc.
        # self.skeleton.add_arc(..., time=current_time) # <- not now

        # (split_event 2.e) modify the set of lists of active vertices/nodes (SLAV)
        # (split_event 2.e.1) Mark the vertex/node V (pointed to by I) as processed.
        # Implementation note: Modification wrt to original algorithm, do not do it now since the split event may fail.
        # event.v.processed = True # <- now now
        # (split_event 2.e.2) Create two new nodes V1 and V2 with the same coordinates as the intersection point I.
        tmp_lav = event_info.v.lav_ptr
        # Implementation note: we create a dummy vertex to hold the position of the split event in the skeleton,
        # and we make both nodes point to that dummy vertex, so that arcs in the skeleton all reference the same
        # vertex, even though they come from different LAVs and point at either vertex_v1 or vertex_v2.
        split_dummy_vertex = VertexInfo(position=event_info.position, lav_ptr=LAV())
        vertex_v1 = VertexInfo(position=event_info.position, lav_ptr=tmp_lav, split_dummy_vertex=split_dummy_vertex)
        vertex_v2 = VertexInfo(position=event_info.position, lav_ptr=tmp_lav, split_dummy_vertex=split_dummy_vertex)

        # (split_event 2.e.3) search the opposite edge in SLAV (sequentially).
        y, x = None, None
        for lavi in self.slav:
            # Iterate the lav finding the two actual vertices that now define the opposite edge.
            for cand_vertex in lavi:
                # Check if this vertex's right edge is the one we are searching for. If so, the next vertex's left
                # edge should also be the one we are searching for.
                if cand_vertex.next_orig_edge != event_info.opposite_edge:
                    continue

                # Sanity check that the edge is properly linked between two vertices.
                if cand_vertex.next_vertex.prev_orig_edge != event_info.opposite_edge:
                    raise RuntimeError("Next vertex's prev_edge is not the split opposite edge?")

                # Check whether the two sub-points of the opposite edge the ones in the event's subpoly. Note a tight
                # collinearity check is required here, or we risk degenerate results.
                y_cand = cand_vertex
                x_cand = cand_vertex.next_vertex
                if y_cand.position == event_info.position or x_cand.position == event_info.position:
                    # We created a split event some time ago, and now we have become part of the opposite edge's
                    # actual vertices. We can't process this.
                    # Note: this is a degenerate situation. Although it happened in the past, I think it is fixed now.
                    GLOBAL_ALGORITHM_TRACER.on_vertex_became_its_opposite_edge(event_info=event_info)
                    continue

                # Test that the point is in the region defined by the candidate split points.
                test_edge = Edge(start_vertex=y_cand, end_vertex=x_cand, is_original_edge=False)
                in_region = test_edge.is_point_in_edge_region(point=event_info.position)
                if not in_region:
                    continue

                if y == event_info.v or x == event_info.v:
                    # If the vertex that wanted to split the edge is one of the edge's vertices, we should not use it.
                    # Moreover, this is probably a bad event due to inclusive epsilon checks.
                    raise RuntimeError(f"Vertex {event_info.v} is one of the vertices of the opposite edge.")
                    # continue

                # Found
                y, x = y_cand, x_cand
                break

            # Do not check more lavs, we already found the vertices.
            if y is not None and x is not None:
                break

        # It is possible that we do not find the proper new vertices for the opposite edge, specifically when the edge
        # has collpased due to other events. If this happens, we should not flag the vertex as processed, so it can
        # have other events attempted.
        if y is None or x is None:
            GLOBAL_ALGORITHM_TRACER.on_failed_to_find_opposite_edge(event_info=event_info)
            # The opposite edge has collapsed, so we can't split it. But perhaps there are other that we can still
            # split. Give this vertex a second chance. This can often happen with reflex vertices that interrupt
            # the split events of other reflex vertices.
            self._attempt_requeue_vertex_events(vi=event_info.v)
            return

        # If we reach here, we can now process the event. Do the things we postponed earlier.
        self.skeleton.add_arc(vertex_1=event_info.v, vertex_2=split_dummy_vertex, at_time=current_time)
        event_info.v.processed = True

        # (split_event 2.e.4) insert both new nodes into the SLAV (break one LAV into two parts).
        # Implementation note: The paper does not describe what to do when the opposite edge is not part of the
        # lav that the event's vertex is part of. Empirically, this happens often in polygons with holes, and that
        # the expected result is to merge the two lavs into a single one. I also tested modifying the lavs as separate
        # ones and it did not yield good results, but would need to prove it.
        event_lav = event_info.v.lav_ptr
        is_multi_lav = event_lav != y.lav_ptr
        self.slav.remove(event_lav)

        # Insert nodes into the lav(s).
        if is_multi_lav:
            # Remove the lav where the points are, since we will merge it with the new lav.
            self.slav.remove(y.lav_ptr)
            # From two lavs, we merge them into a single one by connecting them with V1 and V2.
            #   [... M, Event, N ...]
            #   [... Y, X, ...      ]
            #                         -> [V1, X, ... Y, V2, N, ... M]
            # V1:
            vertex_v1.prev_vertex = event_info.v.prev_vertex
            vertex_v1.next_vertex = x
            # V2:
            vertex_v2.prev_vertex = y
            vertex_v2.next_vertex = event_info.v.next_vertex
            # Important: first set the pointers in both v1 and v2. Then set the pointers in the neighbors.
            vertex_v1.prev_vertex.next_vertex = vertex_v1
            vertex_v1.next_vertex.prev_vertex = vertex_v1
            vertex_v2.prev_vertex.next_vertex = vertex_v2
            vertex_v2.next_vertex.prev_vertex = vertex_v2
        else:
            # From one lav, we create two.
            # [X ... M, Event, N, ... Y]
            #                            -> [V1, X ... M]
            #                            -> [V2, N ... Y]
            # V1:
            vertex_v1.prev_vertex = event_info.v.prev_vertex
            vertex_v1.next_vertex = x
            # V2:
            vertex_v2.prev_vertex = y
            vertex_v2.next_vertex = event_info.v.next_vertex
            # Important: first set the pointers in both v1 and v2. Then set the pointers in the neighbors.
            vertex_v1.prev_vertex.next_vertex = vertex_v1
            vertex_v1.next_vertex.prev_vertex = vertex_v1
            vertex_v2.prev_vertex.next_vertex = vertex_v2
            vertex_v2.next_vertex.prev_vertex = vertex_v2

        # Create new lavs with updated lav pointers.
        new_lavs = []
        lav1 = LAV(head=vertex_v1)
        lav1_len = 0
        for v in lav1:
            v.lav_ptr = lav1
            lav1_len += 1
        new_lavs.append((lav1, lav1_len))

        creates_two_lavs = not is_multi_lav  # multi_lav input => single_lav output
        if creates_two_lavs:
            lav2 = LAV(head=vertex_v2)
            lav2_len = 0
            for v in lav2:
                v.lav_ptr = lav2
                lav2_len += 1
            new_lavs.append((lav2, lav2_len))

        # Add the new lavs, unless they collapse to a single line, in which case we can process immediately as a peak.
        for lavn, lavn_len in new_lavs:
            if lavn_len < 3:
                # If the new lav has less than 3 vertices, it is a line, and we should add it to the skeleton.
                lv1 = lavn.head.next_vertex
                lv2 = lavn.head  # This has to be either vertex_v1 or vertex_v2, so the given time is for that one.
                self.skeleton.add_arc(vertex_1=lv1, vertex_2=lv2, at_time=current_time)
                # Mark the two vertices as processed, since there may still be events in the queue.
                lv1.processed = True
                lv2.processed = True
            else:
                self.slav.add(lavn)

        # (split_event 2.e.5) link the new nodes V1 and V2 with the appropriate edges.
        vertex_v1.prev_orig_edge = vertex_v1.prev_vertex.next_orig_edge
        vertex_v1.next_orig_edge = vertex_v1.next_vertex.prev_orig_edge
        vertex_v2.prev_orig_edge = vertex_v2.prev_vertex.next_orig_edge
        vertex_v2.next_orig_edge = vertex_v2.next_vertex.prev_orig_edge

        # (split_event 2.f) Compute the events for the new nodes V1 and V2.
        # (split_event 2.f.1) First compute new angle bisectors between the line segments linked to them in step 2e.
        if not vertex_v1.processed:
            vertex_v1.compute_from_edges()
        if not vertex_v2.processed:
            vertex_v2.compute_from_edges()

        # (split_event 2.f.2 and split_event 2.f.3) Compute the events for the new nodes.
        for vertex in [vertex_v1, vertex_v2]:
            if not vertex.processed:
                self._queue_vertex_events(vi=vertex)

    def _compute_skeleton_impl(self, exterior: PointList, holes: list[PointList]) -> Skeleton:
        """Computes the straight skeleton of the polygon defined by the given exterior outline and interior holes.

        Args:
            exterior: List of vertices that define the exterior of the polygon. Must be provided in COUNTER-CLOCKWISE,
                with +X-right and +Y-up.
            holes: List of holes, each as a list of vertices that define the hole. Must be provided in CLOCKWISE order,
                with +X-right and +Y-up (opposite of the exterior vertices).

        Returns:
            The straight skeleton of the polygon defined by the exterior and holes.
        """
        # Reset all auto_id counters so that debugging ids are deterministic.
        VertexInfo.reset_count()
        Edge.reset_count()
        LAV.reset_count()
        EventInfo.reset_count()

        # Initial setup
        self._initialize_from(exterior=exterior, holes=holes)

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # 2. While the priority queue is not empty do:
        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        current_step = 0
        while not self.queue.empty():
            # Start the step.
            current_time = self.queue.peek()[0]
            current_step += 1
            GLOBAL_ALGORITHM_TRACER.on_step_begin(step=current_step, time=current_time, algorithm=self)

            # (2.a) Pop the lowest event from queue and process it.
            _, event_info = self.queue.get()
            GLOBAL_ALGORITHM_TRACER.on_event_popped(
                step=current_step, time=current_time, event_info=event_info, algorithm=self
            )

            # If the event is outside the polygon, ignore it. We should probably not queue it in the first place, but
            # leaving it here so we can raise an exception it if it happens.
            if not is_point_inside_polygon_edges(self.original_edges, point2d=event_info.position):
                # If the vertices have been processed, we can ignore the event.
                if event_info.is_edge_event:
                    edge_event_info = cast(EdgeEventInfo, event_info)
                    if edge_event_info.v_a.processed and edge_event_info.v_b.processed:
                        continue
                else:
                    split_event_info = cast(SplitEventInfo, event_info)
                    if split_event_info.v.processed:
                        continue
                # If the vertex is still unprocessed, this would generate a degenerate skeleton, so raise an error.
                # TODO This does happen in real cases. Originally I added it to detect unfinished skeletons, when
                # the last events were detected outside the polygon due to bad LAVs. However I have seen valid
                # cases in which a split event is generated outside the polygon due to the opposite edge collapsing
                # under earlier edge events. We also now detect the former cases during skeleton iteration.
                # raise RuntimeError("Event is still pending, but it is outside the polygon.")
                continue

            # Process the event.
            if event_info.is_edge_event:
                self._process_edge_event(event_info=cast(EdgeEventInfo, event_info), current_time=current_time)
            else:
                self._process_split_event(event_info=cast(SplitEventInfo, event_info), current_time=current_time)

            # We can stop processing events if there are no LAVs, since all vertices are now processed.
            if not self.slav:
                break

        GLOBAL_ALGORITHM_TRACER.on_algorithm_end(algorithm=self)

        return self.skeleton

    def compute_skeleton(self, exterior: PointList, holes: list[PointList]) -> Skeleton:
        """Computes the straight skeleton of the polygon defined by the given exterior outline and interior holes.

        Args:
            exterior: List of vertices that define the exterior of the polygon. Must be provided in COUNTER-CLOCKWISE,
                with +X-right and +Y-up.
            holes: List of holes, each as a list of vertices that define the hole. Must be provided in CLOCKWISE order,
                with +X-right and +Y-up (opposite of the exterior vertices).

        Returns:
            The straight skeleton of the polygon defined by the exterior and holes.
        """
        try:
            return self._compute_skeleton_impl(exterior=exterior, holes=holes)
        except Exception as e:
            GLOBAL_ALGORITHM_TRACER.on_algorith_raised_exception(algorithm=self, exception=e)
            raise e
