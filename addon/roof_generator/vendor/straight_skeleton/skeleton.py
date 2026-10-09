# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterator, TypeAlias

from .constants import NONCOLLINEARITY_EPSILON_DEGS, TIME_EPSILON
from .polygon_math import Edge, VertexInfo
from .vector_math import Orientation, Vector2


class SkeletonNode:
    """Internal representation of vertices in the skeleton (aka nodes)."""

    def __init__(self, sk_id: int, position: Vector2, time: float):
        """Initialize a skeleton node with a given id, and its position and a time."""
        self._skn_id = sk_id
        self.position = position
        self.time = time

    def __repr__(self):
        return f"SKN({self._skn_id}, {self.position.x:.03f}, {self.position.y:.03f}, {self.time:.5f})"


# Undirected link between two nodes.
SkeletonArc: TypeAlias = tuple[SkeletonNode, SkeletonNode]

# List of indices. The indices are the node ids and also expected to be indexing into the list of all nodes in the
# skeleton.
SkeletonFace: TypeAlias = list[int]


class Skeleton:
    """Straight skeleton of a polygon. The skeleton is a graph of nodes and the arcs that connect them. Additionally,
    this class provides the time per node (=the distance from the original polygon edges), and computation of faces,
    so that the polygon can be triangulated and lifted.
    """

    def __init__(self, original_edges: list[Edge]):
        """Initialize the skeleton with the original edges of the polygon."""
        self._sk_nodes_all: list[SkeletonNode] = []
        self._sk_nodes_dummy_only: list[SkeletonNode] = []
        self._vertex_id_to_sk_node_id: dict[int, int] = {}  # This cache may be low hit, except at roof peaks.

        # _arcs_by_node: Bidirectional arcs by node id.
        self._arcs_by_node: dict[int, list[int]] = defaultdict(list)
        # _iteration_arc_list: Iterates arcs in one direction (creation direction), for example for plotting.
        self._iteration_arc_list: list[SkeletonArc] = []

        self._faces: list[SkeletonFace] | None = None

        # For every original edge, we create an initial skeleton node, and then we link them.
        self._sk_original_edges = []
        for edge in original_edges:
            self._add_skeleton_node(for_vertex=edge.start_vertex, at_time=0.0)
        for edge in original_edges:
            e_v_1 = self._find_skeleton_node(edge.start_vertex)
            e_v_2 = self._find_skeleton_node(edge.end_vertex)
            self._sk_original_edges.append((e_v_1._skn_id, e_v_2._skn_id))

    def _add_skeleton_node(self, for_vertex: VertexInfo, at_time: float) -> SkeletonNode:
        """Add an internal node from the given external vertex, at the given time.

        Args:
            vertex: External vertex to add to the skeleton.
            at_time: Time of the vertex, which is the distance from the original polygon edges.

        Returns:
            The newly created skeleton node.
        """
        next_id = len(self._sk_nodes_all)
        new_node = SkeletonNode(sk_id=next_id, position=for_vertex.position, time=at_time)
        self._sk_nodes_all.append(new_node)  # Possible optimization, do not build the list until finished.
        self._vertex_id_to_sk_node_id[for_vertex._auto_id] = new_node._skn_id
        return new_node

    def _find_skeleton_node(self, for_vertex: VertexInfo) -> SkeletonNode:
        """Find the skeleton node corresponding to the given external vertex, and raise an error if not found.

        Args:
            vertex: External vertex to find its corresponding skeleton node.

        Raises:
            RuntimeError: If the node is not found in the skeleton.

        Returns:
            The skeleton node corresponding to the given external vertex.
        """
        sk_vertex_id = self._vertex_id_to_sk_node_id.get(for_vertex._auto_id)
        if sk_vertex_id is not None:
            return self._sk_nodes_all[sk_vertex_id]
        raise RuntimeError(f"Expected vertex not found in skeleton: {for_vertex} vs \n{self._sk_nodes_all}")

    def _find_or_add_skeleton_node(self, for_vertex: VertexInfo, at_time: float) -> SkeletonNode:
        """Find the skeleton node corresponding to the given external vertex, or create a new one if not found.

        If the node is found, the time previously stored must match the given time, otherwise an error is raised.
        If the given time is 0, this method should not be called, and `_find_skeleton_node()` should be used instead,
        since the original vertices are expected to be found after construction, as long as original edges are properly
        specified.

        Args:
            vertex: External vertex to find or add to the skeleton.
            at_time: Time of the vertex, which is the distance from the original polygon edges.

        Raises:
            ValueError: If the time is zero, since you should call `_find_skeleton_node()` instead.
            RuntimeError: If the node is found but the given time does not match the stored time.

        Returns:
            The skeleton node corresponding to the given external vertex.
        """
        # If the time is zero, we should have expected the node to exist.
        if abs(at_time) <= TIME_EPSILON:
            raise ValueError("Zero time should have called `_find_skeleton_node()` instead.")

        # If a skeleton node was already present, we can avoid searching for it.
        sk_node_id = self._vertex_id_to_sk_node_id.get(for_vertex._auto_id)
        if sk_node_id is not None:
            return self._sk_nodes_all[sk_node_id]

        # Search in dummy nodes one that matches the position and the given time.
        for sk_dummy_node in self._sk_nodes_dummy_only:
            if sk_dummy_node.position == for_vertex.position:
                # We found a dummy at that location, check the times.
                if abs(sk_dummy_node.time - at_time) <= TIME_EPSILON:
                    # Times match, we can return this one (and cache the mapping).
                    self._vertex_id_to_sk_node_id[for_vertex._auto_id] = sk_dummy_node._skn_id
                    return sk_dummy_node
                else:
                    # Times do not match, this is an error, since the positions overlap and thus require the same time.
                    raise RuntimeError(
                        f"Nodes at the same position but different time: {for_vertex} vs {sk_dummy_node}\n"
                        + f"  new time:{at_time} vs old time:{sk_dummy_node.time} (diff={abs(sk_dummy_node.time - at_time)})\n"
                        + f"  new position     : {for_vertex.position.x}, \t{for_vertex.position.y}\n"
                        + f"  vs node position : {sk_dummy_node.position.x}, \t{sk_dummy_node.position.y}\n"
                        + f"  diff             : {abs(for_vertex.position.x-sk_dummy_node.position.x)}, \t{abs(for_vertex.position.y-sk_dummy_node.position.y)}"
                    )

        # We did not find one, we have to create a new dummy node (and cache in the dummy list).
        new_dummy_node = self._add_skeleton_node(for_vertex=for_vertex, at_time=at_time)
        self._sk_nodes_dummy_only.append(new_dummy_node)
        return new_dummy_node

    def add_arc(self, vertex_1: VertexInfo, vertex_2: VertexInfo, at_time: float) -> None:
        """Add an arc between the given external vertices, at the given time. Note that the time is a reference to the
        time of the second vertex, and that the first vertex must already exist in the skeleton, either as an original
        vertex or as a previously added vertex.

        Args:
            vertex_1: External vertex to connect.
            vertex_2: External vertex to connect.
            at_time: Time at which the second vertex happens.
        """
        # If any of the vertices are from a split event, link to their dummy vertex instead.
        if vertex_1.split_dummy_vertex is not None:
            vertex_1 = vertex_1.split_dummy_vertex
        if vertex_2.split_dummy_vertex is not None:
            vertex_2 = vertex_2.split_dummy_vertex

        # Find the skeleton nodes for the given vertices.
        sk_node_1 = self._find_skeleton_node(for_vertex=vertex_1)
        sk_node_2 = self._find_or_add_skeleton_node(for_vertex=vertex_2, at_time=at_time)
        skn_id_1, skn_id_2 = sk_node_1._skn_id, sk_node_2._skn_id

        # If they are the same, we should not add an arc, since it's a self referencing arc.
        if skn_id_1 == skn_id_2:
            # We could log this, although it is expected when two edges collapse at the same meeting point.
            return

        # Now add the connection between the nodes.
        self._arcs_by_node[skn_id_1].append(skn_id_2)
        self._arcs_by_node[skn_id_2].append(skn_id_1)
        self._iteration_arc_list.append((sk_node_1, sk_node_2))

    def _compute_faces_if_needed(self) -> None:
        """Compute the faces that the polygon is divided into by the skeleton, and store them in the instance.

        Raises:
            RuntimeError: If the faces could not be computed, for example if the skeleton is not a valid skeleton graph.
        """
        if self._faces is not None:
            return

        # Sanity check that each node has its index as it's node id.
        for idx, sk_v in enumerate(self._sk_nodes_all):
            if sk_v._skn_id != idx:
                raise RuntimeError(f"Node id mismatch: {sk_v._skn_id} vs {idx}")

        faces = []
        # Each original edge causes a face. We can iterate the skeleton to find loops.
        # o1 -> o2 -> sk1 ... skn -> o1
        # Options/Heuristics:
        #   1) DFS, in which loops ending at a visited node or an original other than o1 are discarded.
        #   2) Follow the smallest internal angle at each node. <-- We'll do this.
        for skn_id_1, skn_id_2 in self._sk_original_edges:
            face: SkeletonFace = []

            # Grab the two nodes of the original edge.
            node1, cur_node = self._sk_nodes_all[skn_id_1], self._sk_nodes_all[skn_id_2]
            face.append(node1._skn_id)

            # Iterate the next possible nodes and pick the smallest interior angle.
            prev_node = node1
            visited_arcs = set()
            while cur_node != node1:
                arc = (prev_node._skn_id, cur_node._skn_id)
                if arc in visited_arcs:
                    raise RuntimeError("Face traversal repeats an arc without closing its initiating edge.")
                visited_arcs.add(arc)
                face.append(cur_node._skn_id)
                # Find the next node with the smallest interior angle (they are left angles, so minimize cosine=dot).
                cur_dir = (cur_node.position - prev_node.position).normalized()
                next_node = None
                min_cos = math.inf
                for next_id in self._arcs_by_node[cur_node._skn_id]:
                    # We can't traverse the same arc back.
                    if next_id == prev_node._skn_id:
                        continue
                    if next_id == cur_node._skn_id:
                        raise RuntimeError(f"Found arc to self: {cur_node}")
                    # Check the direction of this arc.
                    cand_node = self._sk_nodes_all[next_id]
                    cand_dir = (cand_node.position - cur_node.position).normalized()
                    cand_ori = Orientation.of_vec_with_respect_to(
                        vec=cand_dir, wrt=cur_dir, collinearity_epsilon_degrees=NONCOLLINEARITY_EPSILON_DEGS
                    )
                    if cand_ori.is_opposite():
                        # Opposite, we should not have this.
                        raise RuntimeError(f"Found opposite arc to non-prev node: {cur_node} -> {cand_node}")
                    # If this arc has the smallest angle so far, keep it.
                    cos_angle = cur_dir.dot(cand_dir)
                    if cand_ori.is_right_exclusive():
                        cos_angle = 2.0 - cos_angle  # For concave, re-scale the cosine [-1, 1] -> [3, 1]
                    if cos_angle < min_cos:
                        min_cos = cos_angle
                        next_node = cand_node
                # We should have found a new node, and it should not be the current one.
                if next_node is None or next_node == cur_node:
                    raise RuntimeError(f"Failed to find a proper next node building faces: {next_node}")
                if next_node == node1:
                    # We have closed the loop, we are done.
                    face.append(node1._skn_id)
                    break
                # The new node should not be an original one, since that means that we did not close the loop.
                if next_node.time <= TIME_EPSILON:
                    raise RuntimeError(f"Ran to an original node {next_node} not part of the initiating edge.")
                prev_node = cur_node
                cur_node = next_node

            # Add the face to the list of faces.
            faces.append(face)

        # We are done, store the faces.
        self._faces = faces

    @property
    def nodes(self) -> list[SkeletonNode]:
        """Get all the nodes in the skeleton, including both polygon-original vertices and additional nodes."""
        return self._sk_nodes_all

    def get_faces(self) -> list[SkeletonFace]:
        """Get the faces that the polygon is divided into by the skeleton, as a list of internal node ids. Note that
        faces will be computed if they have not been cached yet."""
        # Compute faces if not done yet.
        self._compute_faces_if_needed()
        assert self._faces is not None  # For mypy
        return self._faces

    def arc_iterator(self) -> Iterator[tuple[SkeletonNode, SkeletonNode]]:
        """Iterate the arcs in the skeleton, as pairs of nodes that are connected by an arc. Note that this iterator
        iterates the arcs directionally only once, despite the arcs not having a real direction."""
        return iter(self._iteration_arc_list)
