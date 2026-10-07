from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .roof_core import RoofEmbeddingInput
from .roof_graph_io import vertices_2d_to_3d
from .roof_topology import RoofGraphTopology
from .roof_topology import build_roof_graph_topology


@dataclass(frozen=True)
class PrimalRoofEmbedding:
    topology: RoofGraphTopology
    embedding: RoofEmbeddingInput
    initial_vertices: np.ndarray
    fixed_roof_vertex_id: int


def build_primal_roof_embedding(
    vertices_2d: np.ndarray,
    faces,
    roof_height: float = 50.0,
    lambda_weight: float = 0.0,
    fixed_roof_vertex_id: int | None = None,
) -> PrimalRoofEmbedding:
    topology = build_roof_graph_topology(vertices_2d, faces)
    roof_vertex_ids = topology.roof_vertex_ids
    if not roof_vertex_ids:
        raise ValueError("roof graph must contain at least one roof vertex")

    if fixed_roof_vertex_id is None:
        fixed_roof_vertex_id = choose_fixed_roof_vertex(topology)
    elif fixed_roof_vertex_id not in roof_vertex_ids:
        raise ValueError("fixed_roof_vertex_id must refer to a roof vertex")

    initial_vertices = vertices_2d_to_3d(topology.vertices)
    initial_vertices[np.asarray(roof_vertex_ids), 2] = float(roof_height)

    embedding = RoofEmbeddingInput(
        variable_xy_vertex_ids=roof_vertex_ids,
        variable_z_vertex_ids=tuple(vertex_id for vertex_id in roof_vertex_ids if vertex_id != fixed_roof_vertex_id),
        initial_vertices=initial_vertices,
        reference_vertices=np.array(initial_vertices, copy=True),
        faces=topology.faces,
        lambda_weight=lambda_weight,
    )
    return PrimalRoofEmbedding(
        topology=topology,
        embedding=embedding,
        initial_vertices=initial_vertices,
        fixed_roof_vertex_id=fixed_roof_vertex_id,
    )


def choose_fixed_roof_vertex(topology: RoofGraphTopology) -> int:
    return topology.roof_vertex_ids[0]