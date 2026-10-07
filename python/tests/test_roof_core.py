import sys
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blender_adapter import build_comparison_mesh_specs
from blender_adapter import build_boundary_edge_role_preset
from blender_adapter import build_mesh_attribute_payload
from blender_adapter import ensure_roof_vertex_primal_graph
from blender_adapter import generate_primal_graph_from_boundary_roles
from blender_adapter import load_roof_result_json
from blender_adapter import lift_local_vertices_to_world
from blender_adapter import MeshSpec
from blender_adapter import project_planar_mesh_to_primal
from blender_adapter import resolve_planar_mesh_input
from blender_adapter import resolve_primal_graph_faces
from blender_adapter import solve_planar_mesh_to_mesh_specs
from blender_adapter import solve_planar_mesh_with_role_preset_to_mesh_specs
from blender_adapter import solve_primal_graph_to_mesh_specs
from blender_adapter import summarize_single_primitive_preview_input
from blender_adapter import summarize_planar_input
from blender_adapter import summarize_result
from blender_generate_roof_from_mesh import describe_mesh_input
from blender_generate_roof_from_mesh import extract_boundary_edge_roles
from blender_generate_roof_from_mesh import extract_boundary_edge_roles_with_source
from blender_import_roof_result import write_mesh_spec_attributes
from blender_roof_role_props import clear_roof_edge_roles
from blender_roof_graph_props import decode_primal_graph_faces
from blender_roof_graph_props import encode_primal_graph_faces
from blender_roof_graph_props import extract_polygon_faces
from blender_roof_graph_props import store_roof_graph_metadata
from blender_roof_graph_props import store_primal_graph_faces
from blender_roof_role_props import normalize_roof_role_code
from blender_roof_role_props import read_roof_edge_roles
from blender_roof_role_props import set_selected_roof_edge_role
from blender_roof_role_props import store_roof_edge_roles
from blender_roof_role_props import summarize_roof_edge_roles
from blender_roof_solver_props import decode_solver_config
from blender_roof_solver_props import encode_solver_config
from blender_roof_solver_props import read_solver_config
from blender_roof_solver_props import resolve_solver_config
from blender_roof_solver_props import store_solver_config
from core.roof_dual import build_primal_roof_graph_from_dual
from core.roof_core import RoofEmbeddingInput
from core.roof_core import face_planarity_energy
from core.roof_generator import EDGE_ROLE_EAVE
from core.roof_generator import EDGE_ROLE_GABLE_END
from core.roof_generator import EDGE_ROLE_IGNORE
from core.roof_generator import ROOF_ROLE_EAVE
from core.roof_generator import ROOF_ROLE_GABLE_END
from core.roof_generator import ROOF_ROLE_NONE
from core.roof_generator import ROOF_ROLE_SHED_HIGH
from core.roof_generator import ROOF_ROLE_SHED_LOW
from core.roof_generator import EDGE_ROLE_SHED_HIGH
from core.roof_generator import EDGE_ROLE_SHED_LOW
from core.roof_generator import generate_rectangular_roof_graph_from_edge_roles
from core.roof_generator import generate_rectangular_gable_roof_graph
from core.roof_generator import generate_rectangular_shed_roof_graph
from core.roof_graph_io import read_dual_roof_graph
from core.roof_graph_io import read_primal_roof_graph
from core.roof_graph_io import vertices_2d_to_3d
from core.roof_pipeline import build_primal_roof_embedding
from core.roof_core import roof_graph_energy
from core.roof_runner import solve_dual_roof_graph
from core.roof_runner import solve_primal_roof_graph
from core.roof_topology_adapter import preview_generated_roof_graph
from core.roof_topology_adapter import solve_generated_roof_graph
from core.roof_topology_generator import build_footprint_loop
from core.roof_topology_generator import build_l_shaped_gable_roof_graph
from core.roof_topology_generator import build_orthogonal_gable_roof_graph
from core.roof_topology_generator import build_single_primitive_roof_graph
from core.roof_topology_generator import classify_primitive_kind
from core.roof_topology_generator import decompose_orthogonal_footprint_into_primitives
from core.roof_topology_generator import generate_single_primitive_roof_graph_from_edge_roles
from core.roof_topology_generator import PrimitiveKind
from core.roof_topology_generator import RoofRole
from core.roof_topology import build_roof_graph_topology
from core.roof_topology import extract_edges_from_faces
from core.roof_core import update_variable_vertex_positions
from core.roof_topology_generator import UnsupportedTopologyError


class RoofCoreTests(unittest.TestCase):
    def test_update_variable_vertex_positions_updates_xy_and_z_slots(self):
        initial_vertices = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.5],
                [1.0, 1.0, 1.0],
            ]
        )

        updated = update_variable_vertex_positions(
            np.array([10.0, 11.0, 20.0, 21.0, 7.5]),
            variable_xy_vertex_ids=[0, 2],
            variable_z_vertex_ids=[1],
            initial_vertices=initial_vertices,
        )

        expected = np.array(
            [
                [10.0, 11.0, 0.0],
                [1.0, 0.0, 7.5],
                [20.0, 21.0, 1.0],
            ]
        )
        np.testing.assert_allclose(updated, expected)

    def test_face_planarity_energy_is_near_zero_for_planar_face(self):
        vertices = np.array(
            [
                [0.0, 0.0, 2.0],
                [1.0, 0.0, 2.0],
                [1.0, 1.0, 2.0],
                [0.0, 1.0, 2.0],
            ]
        )

        energy = face_planarity_energy(vertices, [(0, 1, 2, 3)])

        self.assertLess(energy, 1e-12)

    def test_face_planarity_energy_increases_for_non_planar_face(self):
        vertices = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.0, 1.0, 1.0],
            ]
        )

        energy = face_planarity_energy(vertices, [(0, 1, 2, 3)])

        self.assertGreater(energy, 0.0)

    def test_roof_graph_energy_adds_xy_regularization(self):
        initial_vertices = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
            ]
        )
        reference_vertices = np.array(initial_vertices, copy=True)
        embedding = RoofEmbeddingInput(
            variable_xy_vertex_ids=(0,),
            variable_z_vertex_ids=(),
            initial_vertices=initial_vertices,
            reference_vertices=reference_vertices,
            faces=((0, 1, 2),),
            lambda_weight=2.0,
        )

        energy = roof_graph_energy(np.array([3.0, 4.0]), embedding)

        self.assertAlmostEqual(energy, 10.0, places=8)

    def test_read_primal_roof_graph_parses_vertices_and_faces(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir) / "sample"
            base_path.with_suffix(".verts").write_text("0,0\n1,0\n1,1\n0,1\n", encoding="ascii")
            base_path.with_suffix(".faces").write_text("0,1,2,3,0\n", encoding="ascii")

            vertices_2d, faces = read_primal_roof_graph(base_path)

        np.testing.assert_allclose(vertices_2d, np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]))
        self.assertEqual(faces, ((0, 1, 2, 3),))

    def test_read_dual_roof_graph_parses_outline_and_adjacency(self):
        base_path = Path(__file__).resolve().parent / "fixtures" / "authored_hip" / "sample"

        outline_vertices, adjacency = read_dual_roof_graph(base_path)

        self.assertEqual(outline_vertices.shape, (4, 2))
        self.assertEqual(adjacency.shape, (4, 4))
        self.assertEqual(int(adjacency[0, 1]), 1)
        self.assertEqual(int(adjacency[1, 0]), 1)
        self.assertEqual(int(adjacency[1, 3]), 0)

    def test_vertices_2d_to_3d_adds_constant_z_column(self):
        vertices_3d = vertices_2d_to_3d(np.array([[2.0, 3.0], [4.0, 5.0]]), z_value=7.0)

        np.testing.assert_allclose(vertices_3d, np.array([[2.0, 3.0, 7.0], [4.0, 5.0, 7.0]]))

    def test_extract_edges_from_faces_returns_unique_undirected_edges(self):
        edges = extract_edges_from_faces([(0, 1, 2), (2, 1, 3)])

        self.assertEqual(edges, ((0, 1), (0, 2), (1, 2), (1, 3), (2, 3)))

    def test_build_roof_graph_topology_classifies_authored_hip(self):
        base_path = Path(__file__).resolve().parent / "fixtures" / "authored_hip" / "sample"
        vertices_2d, faces = read_primal_roof_graph(base_path)

        topology = build_roof_graph_topology(vertices_2d, faces)

        self.assertEqual(topology.outline_vertex_ids, (0, 1, 2, 3))
        self.assertEqual(topology.roof_vertex_ids, (4, 5))
        self.assertEqual(len(topology.outline_edge_ids), 4)
        self.assertEqual(topology.outline_contour, (0, 1, 2, 3))
        adjacent, shared_edge_ids = topology.are_faces_adjacent(0, 1)
        self.assertTrue(adjacent)
        self.assertEqual(len(shared_edge_ids), 1)

    def test_roof_graph_topology_query_helpers_match_authored_hip(self):
        base_path = Path(__file__).resolve().parent / "fixtures" / "authored_hip" / "sample"
        vertices_2d, faces = read_primal_roof_graph(base_path)

        topology = build_roof_graph_topology(vertices_2d, faces)

        self.assertEqual(set(topology.face_roof_vertex_ids(0)), {4, 5})
        self.assertEqual(len(topology.face_outline_edge_ids(0)), 1)
        self.assertEqual(len(topology.face_ridge_edge_ids(0)), 1)
        self.assertEqual(topology.neighboring_face_ids(0), (1, 2, 3))
        self.assertEqual(topology.neighboring_vertex_ids(4), (0, 3, 5))
        self.assertEqual(topology.neighboring_face_ids_of_vertex(4), (0, 2, 3))
        self.assertEqual(topology.neighboring_outline_vertex_ids(0), (3, 1))
        self.assertEqual(topology.edge_edit_type(topology.face_ridge_edge_ids(0)[0]), 1)
        is_simple, problematic_edge_ids = topology.is_graph_simple()
        self.assertTrue(is_simple)
        self.assertEqual(problematic_edge_ids, ())

    def test_build_primal_roof_graph_from_dual_reconstructs_authored_hip_faces(self):
        base_path = Path(__file__).resolve().parent / "fixtures" / "authored_hip" / "sample"
        outline_vertices, adjacency = read_dual_roof_graph(base_path)
        expected_vertices, expected_faces = read_primal_roof_graph(base_path)

        primal_graph = build_primal_roof_graph_from_dual(outline_vertices, adjacency)

        np.testing.assert_allclose(primal_graph.vertices[: len(outline_vertices)], outline_vertices)
        self.assertEqual(primal_graph.vertices.shape, expected_vertices.shape)
        # Interior vertex labels are arbitrary; boundary labels and incidence
        # must agree with the authored hip graph, up to its two ridge labels.
        swapped = tuple(tuple(9-i if i in (4, 5) else i for i in face) for face in primal_graph.faces)
        self.assertIn(_canonicalize_faces(expected_faces),
                      (_canonicalize_faces(primal_graph.faces), _canonicalize_faces(swapped)))

    def test_build_roof_graph_topology_removes_unreferenced_vertices(self):
        vertices = np.array(
            [
                [0.0, 0.0],
                [1.0, 0.0],
                [0.0, 1.0],
                [10.0, 10.0],
            ]
        )
        topology = build_roof_graph_topology(vertices, [(0, 1, 2)])

        self.assertEqual(topology.vertices.shape, (3, 2))
        self.assertEqual(topology.faces, ((0, 1, 2),))

    def test_build_primal_roof_embedding_prepares_default_optimization_inputs(self):
        base_path = Path(__file__).resolve().parent / "fixtures" / "authored_hip" / "sample"
        vertices_2d, faces = read_primal_roof_graph(base_path)

        primal_embedding = build_primal_roof_embedding(vertices_2d, faces, roof_height=25.0, lambda_weight=0.1)

        self.assertEqual(primal_embedding.initial_vertices.shape, (6, 3))
        self.assertEqual(primal_embedding.embedding.variable_xy_vertex_ids, (4, 5))
        self.assertEqual(primal_embedding.embedding.variable_z_vertex_ids, (5,))
        self.assertEqual(primal_embedding.fixed_roof_vertex_id, 4)
        self.assertTrue(np.allclose(primal_embedding.initial_vertices[list(primal_embedding.topology.outline_vertex_ids), 2], 0.0))
        self.assertTrue(np.allclose(primal_embedding.initial_vertices[list(primal_embedding.topology.roof_vertex_ids), 2], 25.0))

    def test_generate_rectangular_gable_roof_graph_builds_expected_primal_graph(self):
        outline_vertices = np.array(
            [
                [0.0, 0.0],
                [4.0, 0.0],
                [4.0, 2.0],
                [0.0, 2.0],
            ]
        )

        generated = generate_rectangular_gable_roof_graph(
            outline_vertices,
            (EDGE_ROLE_EAVE, EDGE_ROLE_GABLE_END, EDGE_ROLE_EAVE, EDGE_ROLE_GABLE_END),
        )

        np.testing.assert_allclose(generated.vertices_2d[4], np.array([4.0, 1.0]))
        np.testing.assert_allclose(generated.vertices_2d[5], np.array([0.0, 1.0]))
        self.assertEqual(
            _canonicalize_faces(generated.faces),
            _canonicalize_faces(((2, 3, 5, 4), (4, 5, 0, 1), (1, 4, 2), (3, 5, 0))),
        )

        topology = build_roof_graph_topology(generated.vertices_2d, generated.faces)
        self.assertEqual(topology.roof_vertex_ids, (4, 5))
        self.assertEqual(len(topology.faces), 4)

    def test_generated_rectangular_gable_roof_graph_solves_through_existing_optimizer(self):
        outline_vertices = np.array(
            [
                [0.0, 0.0],
                [4.0, 0.0],
                [4.0, 2.0],
                [0.0, 2.0],
            ]
        )

        generated = generate_rectangular_gable_roof_graph(
            outline_vertices,
            (EDGE_ROLE_EAVE, EDGE_ROLE_GABLE_END, EDGE_ROLE_EAVE, EDGE_ROLE_GABLE_END),
        )
        result = solve_primal_roof_graph(generated.vertices_2d, generated.faces, roof_height=3.0, lambda_weight=0.0)

        self.assertTrue(result.optimizer_success)
        self.assertEqual(len(result.optimized_vertices), 6)
        self.assertEqual(len(result.faces), 4)
        self.assertLessEqual(result.planarity_after, result.planarity_before + 1e-12)

    def test_generate_rectangular_shed_roof_graph_builds_expected_primal_graph(self):
        outline_vertices = np.array(
            [
                [0.0, 0.0],
                [4.0, 0.0],
                [4.0, 2.0],
                [0.0, 2.0],
            ]
        )

        generated = generate_rectangular_shed_roof_graph(
            outline_vertices,
            (EDGE_ROLE_SHED_LOW, EDGE_ROLE_IGNORE, EDGE_ROLE_SHED_HIGH, EDGE_ROLE_IGNORE),
        )

        np.testing.assert_allclose(generated.vertices_2d[4], np.array([4.0, 2.0]))
        np.testing.assert_allclose(generated.vertices_2d[5], np.array([0.0, 2.0]))
        self.assertEqual(
            _canonicalize_faces(generated.faces),
            _canonicalize_faces(((0, 1, 4, 5), (1, 2, 4), (4, 2, 3, 5), (3, 5, 0))),
        )

        topology = build_roof_graph_topology(generated.vertices_2d, generated.faces)
        self.assertEqual(topology.roof_vertex_ids, (4, 5))
        self.assertEqual(len(topology.faces), 4)

    def test_generated_rectangular_shed_roof_graph_solves_through_existing_optimizer(self):
        outline_vertices = np.array(
            [
                [0.0, 0.0],
                [4.0, 0.0],
                [4.0, 2.0],
                [0.0, 2.0],
            ]
        )

        generated = generate_rectangular_shed_roof_graph(
            outline_vertices,
            (EDGE_ROLE_SHED_LOW, EDGE_ROLE_IGNORE, EDGE_ROLE_SHED_HIGH, EDGE_ROLE_IGNORE),
        )
        result = solve_primal_roof_graph(generated.vertices_2d, generated.faces, roof_height=3.0, lambda_weight=0.0)

        self.assertTrue(result.optimizer_success)
        self.assertEqual(len(result.optimized_vertices), 6)
        self.assertEqual(len(result.faces), 4)
        self.assertLessEqual(result.planarity_after, result.planarity_before + 1e-12)

    def test_generate_rectangular_roof_graph_from_edge_roles_accepts_integer_gable_roles(self):
        outline_vertices = np.array(
            [
                [0.0, 0.0],
                [4.0, 0.0],
                [4.0, 2.0],
                [0.0, 2.0],
            ]
        )

        generated = generate_rectangular_roof_graph_from_edge_roles(
            outline_vertices,
            (ROOF_ROLE_EAVE, ROOF_ROLE_GABLE_END, ROOF_ROLE_EAVE, ROOF_ROLE_GABLE_END),
        )

        self.assertEqual(generated.edge_roles, (EDGE_ROLE_EAVE, EDGE_ROLE_GABLE_END, EDGE_ROLE_EAVE, EDGE_ROLE_GABLE_END))
        self.assertEqual(len(generated.vertices_2d), 6)

    def test_build_footprint_loop_removes_collinear_vertices_and_stabilizes_winding(self):
        footprint = build_footprint_loop(
            [(0.0, 0.0), (2.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0)],
            [RoofRole.NONE, RoofRole.NONE, RoofRole.NONE, RoofRole.NONE, RoofRole.NONE],
        )

        self.assertEqual(len(footprint.vertices), 4)
        self.assertEqual(classify_primitive_kind(footprint), PrimitiveKind.RECTANGLE)
        signed_area = 0.0
        for index, vertex in enumerate(footprint.vertices):
            x0, y0 = vertex
            x1, y1 = footprint.vertices[(index + 1) % len(footprint.vertices)]
            signed_area += x0 * y1 - x1 * y0
        self.assertGreater(signed_area, 0.0)

    def test_classify_primitive_kind_detects_oblique_quad(self):
        footprint = build_footprint_loop(
            [(0.0, 0.0), (4.0, 0.0), (5.0, 2.0), (1.0, 2.0)],
            [RoofRole.NONE, RoofRole.NONE, RoofRole.NONE, RoofRole.NONE],
        )

        self.assertEqual(classify_primitive_kind(footprint), PrimitiveKind.OBLIQUE_QUAD)

    def test_decompose_orthogonal_footprint_into_primitives_splits_l_shape_into_rectangles(self):
        footprint = build_footprint_loop(
            [(0.0, 0.0), (4.0, 0.0), (4.0, 1.0), (2.0, 1.0), (2.0, 2.0), (0.0, 2.0)],
            [RoofRole.NONE] * 6,
        )

        primitives = decompose_orthogonal_footprint_into_primitives(footprint)

        self.assertEqual(len(primitives), 2)
        self.assertTrue(all(primitive.kind == PrimitiveKind.RECTANGLE for primitive in primitives))
        total_area = sum(
            (primitive.polygon[1][0] - primitive.polygon[0][0])
            * (primitive.polygon[2][1] - primitive.polygon[1][1])
            for primitive in primitives
        )
        self.assertAlmostEqual(total_area, 6.0)
        self.assertTrue(any(primitive.polygon == ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)) for primitive in primitives))
        self.assertTrue(any(primitive.polygon == ((2.0, 0.0), (4.0, 0.0), (4.0, 1.0), (2.0, 1.0)) for primitive in primitives))

    def test_decompose_orthogonal_footprint_into_primitives_keeps_rectangle_single(self):
        footprint = build_footprint_loop(
            [(0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0)],
            [RoofRole.NONE] * 4,
        )

        primitives = decompose_orthogonal_footprint_into_primitives(footprint)

        self.assertEqual(len(primitives), 1)
        self.assertEqual(primitives[0].kind, PrimitiveKind.RECTANGLE)

    def test_build_l_shaped_gable_roof_graph_generates_merged_ridge_topology(self):
        footprint = build_footprint_loop(
            [(0.0, 0.0), (4.0, 0.0), (4.0, 1.0), (2.0, 1.0), (2.0, 2.0), (0.0, 2.0)],
            [RoofRole.NONE] * 6,
        )

        roof_graph = build_l_shaped_gable_roof_graph(footprint, roof_height=2.0)

        self.assertEqual(roof_graph.roof_kind, "gable")
        self.assertEqual(roof_graph.primitive_kind, PrimitiveKind.RESIDUAL)
        self.assertEqual(len(roof_graph.vertices_2d), 9)
        self.assertEqual(len(roof_graph.faces), 6)
        self.assertEqual(sum(1 for face in roof_graph.faces if len(face) == 3), 2)
        np.testing.assert_allclose(roof_graph.vertices_2d[6], np.array([4.0, 0.5]))
        np.testing.assert_allclose(roof_graph.vertices_2d[7], np.array([1.0, 2.0]))
        np.testing.assert_allclose(roof_graph.vertices_2d[8], np.array([1.0, 0.5]))
        ridge_edges = sorted(edge for edge, tag in roof_graph.edge_tags.items() if tag == "ridge")
        self.assertEqual(ridge_edges, [(6, 8), (7, 8)])
        self.assertEqual(sum(1 for tag in roof_graph.edge_tags.values() if tag == "gable_end"), 2)

        vertices_3d = vertices_2d_to_3d(roof_graph.vertices_2d, z_value=0.0)
        for vertex_id, z_value in roof_graph.z_hints.items():
            vertices_3d[vertex_id, 2] = z_value
        self.assertLessEqual(face_planarity_energy(vertices_3d, roof_graph.faces), 1e-12)

    def test_build_l_shaped_gable_roof_graph_accepts_explicit_cap_roles(self):
        footprint = build_footprint_loop(
            [(0.0, 0.0), (4.0, 0.0), (4.0, 1.0), (2.0, 1.0), (2.0, 2.0), (0.0, 2.0)],
            [
                RoofRole.EAVE,
                RoofRole.GABLE_END,
                RoofRole.EAVE,
                RoofRole.EAVE,
                RoofRole.GABLE_END,
                RoofRole.EAVE,
            ],
        )

        roof_graph = build_l_shaped_gable_roof_graph(footprint, roof_height=2.0)

        self.assertEqual(len(roof_graph.faces), 6)

    def test_build_l_shaped_gable_roof_graph_rejects_gable_role_on_wing_side(self):
        footprint = build_footprint_loop(
            [(0.0, 0.0), (4.0, 0.0), (4.0, 1.0), (2.0, 1.0), (2.0, 2.0), (0.0, 2.0)],
            [
                RoofRole.GABLE_END,
                RoofRole.NONE,
                RoofRole.NONE,
                RoofRole.NONE,
                RoofRole.NONE,
                RoofRole.NONE,
            ],
        )

        with self.assertRaisesRegex(UnsupportedTopologyError, "wing-end edges"):
            build_l_shaped_gable_roof_graph(footprint, roof_height=2.0)

    def test_build_l_shaped_gable_roof_graph_rejects_two_reflex_outline(self):
        footprint = build_footprint_loop(
            [
                (0.0, 0.0),
                (6.0, 0.0),
                (6.0, 1.0),
                (4.0, 1.0),
                (4.0, 2.0),
                (2.0, 2.0),
                (2.0, 1.0),
                (0.0, 1.0),
            ],
            [RoofRole.NONE] * 8,
        )

        with self.assertRaisesRegex(UnsupportedTopologyError, "six-vertex"):
            build_l_shaped_gable_roof_graph(footprint, roof_height=2.0)

    def test_build_l_shaped_gable_roof_graph_rejects_non_axis_aligned_outline(self):
        footprint = build_footprint_loop(
            [(0.0, 0.0), (4.0, 0.0), (4.0, 1.0), (2.2, 1.1), (2.0, 2.0), (0.0, 2.0)],
            [RoofRole.NONE] * 6,
        )

        with self.assertRaisesRegex(UnsupportedTopologyError, "axis-aligned"):
            build_l_shaped_gable_roof_graph(footprint, roof_height=2.0)

    def test_build_single_primitive_roof_graph_generates_flat_roof(self):
        footprint = build_footprint_loop(
            [(0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0)],
            [RoofRole.NONE, RoofRole.NONE, RoofRole.NONE, RoofRole.NONE],
        )

        roof_graph = build_single_primitive_roof_graph(footprint, roof_height=3.0)
        result = solve_generated_roof_graph(roof_graph)

        self.assertEqual(roof_graph.roof_kind, "flat")
        self.assertEqual(roof_graph.faces, ((0, 1, 2, 3),))
        self.assertTrue(all(abs(z_value - 3.0) <= 1e-12 for z_value in roof_graph.z_hints.values()))
        self.assertTrue(result.optimizer_success)
        self.assertEqual(result.fixed_roof_vertex_id, -1)

    def test_build_single_primitive_roof_graph_generates_oblique_gable_and_solves(self):
        roof_graph = generate_single_primitive_roof_graph_from_edge_roles(
            [(0.0, 0.0), (4.0, 0.0), (5.0, 2.0), (1.0, 2.0)],
            [RoofRole.EAVE, RoofRole.GABLE_END, RoofRole.EAVE, RoofRole.GABLE_END],
            roof_height=3.0,
        )
        result = solve_generated_roof_graph(roof_graph, lambda_weight=0.0)

        np.testing.assert_allclose(roof_graph.vertices_2d[4], np.array([4.5, 1.0]))
        np.testing.assert_allclose(roof_graph.vertices_2d[5], np.array([0.5, 1.0]))
        self.assertEqual(roof_graph.z_hints[4], 3.0)
        self.assertEqual(roof_graph.z_hints[5], 3.0)
        self.assertTrue(result.optimizer_success)
        self.assertEqual(len(result.faces), 4)

    def test_build_single_primitive_roof_graph_generates_shed_and_solves(self):
        footprint = build_footprint_loop(
            [(0.0, 0.0), (4.0, 0.0), (5.0, 2.0), (1.0, 2.0)],
            [RoofRole.SHED_LOW, RoofRole.EAVE, RoofRole.SHED_HIGH, RoofRole.NONE],
        )

        roof_graph = build_single_primitive_roof_graph(footprint, roof_height=3.0)
        result = solve_generated_roof_graph(roof_graph, lambda_weight=0.0)

        self.assertEqual(roof_graph.roof_kind, "shed")
        self.assertEqual(roof_graph.z_hints[4], 3.0)
        self.assertEqual(roof_graph.z_hints[5], 3.0)
        self.assertTrue(result.optimizer_success)
        self.assertEqual(len(result.faces), 4)

    def test_preview_generated_roof_graph_falls_back_to_hint_embedding_when_scipy_is_unavailable(self):
        roof_graph = generate_single_primitive_roof_graph_from_edge_roles(
            [(0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0)],
            [RoofRole.EAVE, RoofRole.GABLE_END, RoofRole.EAVE, RoofRole.GABLE_END],
            roof_height=3.0,
        )

        with patch("core.roof_topology_adapter.solve_primal_roof_graph", side_effect=ImportError("scipy unavailable")):
            result = preview_generated_roof_graph(roof_graph, lambda_weight=0.0)

        self.assertTrue(result.optimizer_success)
        self.assertIn("SciPy is unavailable", result.optimizer_message)
        self.assertEqual(len(result.optimized_vertices), 6)
        self.assertLessEqual(abs(result.planarity_after), 1e-9)

    def test_build_single_primitive_roof_graph_rejects_invalid_gable_patterns(self):
        footprint = build_footprint_loop(
            [(0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0)],
            [RoofRole.GABLE_END, RoofRole.EAVE, RoofRole.EAVE, RoofRole.EAVE],
        )
        adjacent = build_footprint_loop(
            [(0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0)],
            [RoofRole.GABLE_END, RoofRole.GABLE_END, RoofRole.EAVE, RoofRole.EAVE],
        )

        with self.assertRaises(UnsupportedTopologyError):
            build_single_primitive_roof_graph(footprint, roof_height=3.0)
        with self.assertRaises(UnsupportedTopologyError):
            build_single_primitive_roof_graph(adjacent, roof_height=3.0)

    def test_generate_primal_graph_from_boundary_roles_builds_rectangular_gable_graph(self):
        vertices_2d = np.array(
            [
                [0.0, 0.0],
                [4.0, 0.0],
                [4.0, 2.0],
                [0.0, 2.0],
            ]
        )

        resolved_vertices, resolved_faces = generate_primal_graph_from_boundary_roles(
            vertices_2d,
            ((0, 1, 2, 3),),
            {
                (0, 1): ROOF_ROLE_EAVE,
                (1, 2): ROOF_ROLE_GABLE_END,
                (2, 3): ROOF_ROLE_EAVE,
                (0, 3): ROOF_ROLE_GABLE_END,
            },
        )

        self.assertEqual(resolved_vertices.shape, (6, 2))
        self.assertEqual(
            _canonicalize_faces(resolved_faces),
            _canonicalize_faces(((2, 3, 5, 4), (4, 5, 0, 1), (1, 4, 2), (3, 5, 0))),
        )

    def test_build_boundary_edge_role_preset_assigns_shorter_pair_for_gable(self):
        vertices_2d = np.array(
            [
                [0.0, 0.0],
                [4.0, 0.0],
                [4.0, 2.0],
                [0.0, 2.0],
            ]
        )

        edge_roles = build_boundary_edge_role_preset(vertices_2d, ((0, 1, 2, 3),), roof_kind="gable", gable_pair_mode="shorter")

        self.assertEqual(edge_roles[(0, 1)], ROOF_ROLE_EAVE)
        self.assertEqual(edge_roles[(1, 2)], ROOF_ROLE_GABLE_END)
        self.assertEqual(edge_roles[(2, 3)], ROOF_ROLE_EAVE)
        self.assertEqual(edge_roles[(0, 3)], ROOF_ROLE_GABLE_END)

    def test_solve_planar_mesh_with_role_preset_to_mesh_specs_runs_on_boundary_rectangle(self):
        vertices_world = np.array(
            [
                [0.0, 0.0, 0.0],
                [4.0, 0.0, 0.0],
                [4.0, 2.0, 0.0],
                [0.0, 2.0, 0.0],
            ]
        )

        mesh_specs, payload, _frame = solve_planar_mesh_with_role_preset_to_mesh_specs(
            vertices_world,
            ((0, 1, 2, 3),),
            roof_kind="gable",
            mesh_name="preview",
            roof_height=3.0,
            lambda_weight=0.0,
            separation_factor=1.0,
            gable_pair_mode="shorter",
        )

        self.assertEqual(len(mesh_specs), 2)
        self.assertEqual(len(payload["faces"]), 4)
        self.assertEqual(len(payload["optimized_vertices"]), 6)
        self.assertLessEqual(payload["planarity_after"], payload["planarity_before"] + 1e-12)

    def test_solve_planar_mesh_with_role_preset_to_mesh_specs_runs_on_gridded_rectangle(self):
        vertices_world = np.array(
            [
                [0.0, 0.0, 0.0],
                [2.0, 0.0, 0.0],
                [4.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [2.0, 1.0, 0.0],
                [4.0, 1.0, 0.0],
                [0.0, 2.0, 0.0],
                [2.0, 2.0, 0.0],
                [4.0, 2.0, 0.0],
            ]
        )
        faces = (
            (0, 1, 4, 3),
            (1, 2, 5, 4),
            (3, 4, 7, 6),
            (4, 5, 8, 7),
        )

        mesh_specs, payload, _frame = solve_planar_mesh_with_role_preset_to_mesh_specs(
            vertices_world,
            faces,
            roof_kind="gable",
            mesh_name="preview_grid",
            roof_height=3.0,
            lambda_weight=0.0,
            separation_factor=1.0,
            gable_pair_mode="shorter",
        )

        self.assertEqual(len(mesh_specs), 2)
        self.assertEqual(len(payload["faces"]), 4)
        self.assertEqual(len(payload["optimized_vertices"]), 6)
        self.assertLessEqual(payload["planarity_after"], payload["planarity_before"] + 1e-12)

    def test_solve_planar_mesh_with_role_preset_to_mesh_specs_tolerates_noisy_gridded_rectangle(self):
        vertices_world = np.array(
            [
                [0.0, 0.0, 0.0],
                [2.0, 0.0005, 0.0],
                [4.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [2.0, 1.0, 0.0],
                [4.0, 1.0, 0.0],
                [0.0, 2.0, 0.0],
                [2.0, 1.9995, 0.0],
                [4.0, 2.0, 0.0],
            ]
        )
        faces = (
            (0, 1, 4, 3),
            (1, 2, 5, 4),
            (3, 4, 7, 6),
            (4, 5, 8, 7),
        )

        mesh_specs, payload, _frame = solve_planar_mesh_with_role_preset_to_mesh_specs(
            vertices_world,
            faces,
            roof_kind="gable",
            mesh_name="preview_noisy_grid",
            roof_height=3.0,
            lambda_weight=0.0,
            separation_factor=1.0,
            gable_pair_mode="shorter",
        )

        self.assertEqual(len(mesh_specs), 2)
        self.assertEqual(len(payload["faces"]), 4)
        self.assertEqual(len(payload["optimized_vertices"]), 6)
        self.assertLessEqual(payload["planarity_after"], payload["planarity_before"] + 1e-12)

    def test_solve_planar_mesh_with_role_preset_to_mesh_specs_accepts_t_shaped_grid_for_gable(self):
        vertices_world = np.array(
            [
                [0.0, 0.0, 0.0],
                [2.0, 0.0, 0.0],
                [4.0, 0.0, 0.0],
                [6.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [2.0, 1.0, 0.0],
                [4.0, 1.0, 0.0],
                [6.0, 1.0, 0.0],
                [0.0, 2.0, 0.0],
                [2.0, 2.0, 0.0],
                [4.0, 2.0, 0.0],
                [6.0, 2.0, 0.0],
            ]
        )
        faces = (
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (5, 6, 10, 9),
        )

        mesh_specs, payload, _frame = solve_planar_mesh_with_role_preset_to_mesh_specs(
            vertices_world,
            faces,
            roof_kind="gable",
            mesh_name="preview_t_shape",
            roof_height=3.0,
            lambda_weight=0.0,
            separation_factor=1.0,
            gable_pair_mode="shorter",
        )

        self.assertEqual(len(mesh_specs), 2)
        self.assertGreater(len(payload["faces"]), len(faces))
        self.assertLessEqual(abs(payload["planarity_after"]), 1e-9)
        self.assertTrue(payload["optimizer_success"])

    def test_solve_planar_mesh_with_role_preset_to_mesh_specs_accepts_l_shaped_grid_for_gable_preview(self):
        vertices_world = np.array(
            [
                [0.0, 0.0, 0.0],
                [2.0, 0.0, 0.0],
                [4.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [2.0, 1.0, 0.0],
                [4.0, 1.0, 0.0],
                [0.0, 2.0, 0.0],
                [2.0, 2.0, 0.0],
                [4.0, 2.0, 0.0],
            ]
        )
        faces = (
            (0, 1, 4, 3),
            (1, 2, 5, 4),
            (3, 4, 7, 6),
        )

        mesh_specs, payload, _frame = solve_planar_mesh_with_role_preset_to_mesh_specs(
            vertices_world,
            faces,
            roof_kind="gable",
            mesh_name="preview_l_shape_gable",
            roof_height=3.0,
            lambda_weight=0.0,
            separation_factor=1.0,
            gable_pair_mode="shorter",
        )

        self.assertEqual(len(mesh_specs), 2)
        self.assertGreater(len(payload["faces"]), 6)
        self.assertGreater(len(payload["optimized_vertices"]), 9)
        self.assertLessEqual(payload["planarity_after"], 1e-9)
        max_initial_z = max(abs(vertex[2]) for vertex in payload["initial_vertices"])
        self.assertAlmostEqual(max_initial_z, 3.0, places=6)

    def test_build_orthogonal_gable_roof_graph_accepts_fourteen_vertex_residual(self):
        footprint = build_footprint_loop(
            [
                (0.0, 0.0),
                (7.0, 0.0),
                (7.0, 1.0),
                (6.0, 1.0),
                (6.0, 3.0),
                (5.0, 3.0),
                (5.0, 2.0),
                (4.0, 2.0),
                (4.0, 4.0),
                (2.0, 4.0),
                (2.0, 2.0),
                (1.0, 2.0),
                (1.0, 3.0),
                (0.0, 3.0),
            ],
            [RoofRole.NONE] * 14,
        )

        roof_graph = build_orthogonal_gable_roof_graph(footprint, roof_height=3.0)
        topology = build_roof_graph_topology(roof_graph.vertices_2d, roof_graph.faces)
        vertices_3d = vertices_2d_to_3d(roof_graph.vertices_2d, z_value=0.0)
        for vertex_id, z_value in roof_graph.z_hints.items():
            vertices_3d[vertex_id, 2] = z_value
        result = solve_generated_roof_graph(roof_graph, lambda_weight=0.0)

        self.assertEqual(roof_graph.primitive_kind, PrimitiveKind.RESIDUAL)
        self.assertEqual(roof_graph.roof_kind, "gable")
        self.assertGreater(len(topology.roof_vertex_ids), 0)
        self.assertTrue(all(len(face) in {3, 4} for face in roof_graph.faces))
        self.assertTrue(all(len(topology.edge_neighboring_faces(edge_id)) in {1, 2} for edge_id in range(len(topology.edges))))
        self.assertTrue(set(roof_graph.edge_tags).issubset(set(topology.edges)))
        self.assertIn("gable_end", roof_graph.edge_tags.values())
        self.assertIn("eave", roof_graph.edge_tags.values())
        self.assertLessEqual(abs(face_planarity_energy(vertices_3d, roof_graph.faces)), 1e-9)
        self.assertAlmostEqual(max(roof_graph.z_hints.values()), 3.0)
        self.assertTrue(result.optimizer_success)
        self.assertLessEqual(abs(result.planarity_after), 1e-9)

    def test_preview_accepts_grid_matching_reported_complex_input_counts(self):
        occupied_cells = {
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 0),
            (0, 1),
            (1, 1),
            (2, 1),
            (3, 1),
            (4, 1),
            (1, 2),
            (3, 2),
        }
        points = sorted(
            {
                point
                for x_value, y_value in occupied_cells
                for point in (
                    (x_value, y_value),
                    (x_value + 1, y_value),
                    (x_value + 1, y_value + 1),
                    (x_value, y_value + 1),
                )
            },
            key=lambda point: (point[1], point[0]),
        )
        diagonal_basis_point = (1, 1)
        points = [points[0], diagonal_basis_point] + [
            point for point in points[1:] if point != diagonal_basis_point
        ]
        vertex_id_by_point = {point: vertex_id for vertex_id, point in enumerate(points)}
        vertices_world = np.asarray([(x_value, y_value, 0.0) for x_value, y_value in points], dtype=float)
        faces = tuple(
            (
                vertex_id_by_point[(x_value, y_value)],
                vertex_id_by_point[(x_value + 1, y_value)],
                vertex_id_by_point[(x_value + 1, y_value + 1)],
                vertex_id_by_point[(x_value, y_value + 1)],
            )
            for x_value, y_value in sorted(occupied_cells, key=lambda point: (point[1], point[0]))
        )

        input_summary = summarize_planar_input(vertices_world, faces)
        preview_summary = summarize_single_primitive_preview_input(vertices_world, faces)
        mesh_specs, payload, _frame = solve_planar_mesh_with_role_preset_to_mesh_specs(
            vertices_world,
            faces,
            roof_kind="gable",
            mesh_name="preview_reported_complex_grid",
            roof_height=3.0,
            lambda_weight=0.0,
            separation_factor=1.0,
            gable_pair_mode="shorter",
        )

        self.assertEqual(input_summary, "vertices=21, faces=11, outline_vertices=18, roof_vertices=3")
        self.assertEqual(
            preview_summary,
            "raw_outline_vertices=18, simplified_outline_vertices=14, primitive_kind=residual",
        )
        self.assertEqual(len(mesh_specs), 2)
        self.assertTrue(payload["optimizer_success"])
        self.assertLessEqual(abs(payload["planarity_after"]), 1e-9)

    def test_solve_planar_mesh_with_role_preset_to_mesh_specs_accepts_l_shaped_grid_for_flat_preview(self):
        vertices_world = np.array(
            [
                [0.0, 0.0, 0.0],
                [2.0, 0.0, 0.0],
                [4.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [2.0, 1.0, 0.0],
                [4.0, 1.0, 0.0],
                [0.0, 2.0, 0.0],
                [2.0, 2.0, 0.0],
                [4.0, 2.0, 0.0],
            ]
        )
        faces = (
            (0, 1, 4, 3),
            (1, 2, 5, 4),
            (3, 4, 7, 6),
        )

        mesh_specs, payload, _frame = solve_planar_mesh_with_role_preset_to_mesh_specs(
            vertices_world,
            faces,
            roof_kind="flat",
            mesh_name="preview_l_shape_flat",
            roof_height=3.0,
            lambda_weight=0.0,
            separation_factor=1.0,
            gable_pair_mode="shorter",
        )

        self.assertEqual(len(mesh_specs), 2)
        self.assertEqual(len(payload["faces"]), 2)
        self.assertGreaterEqual(len(payload["optimized_vertices"]), 6)
        self.assertAlmostEqual(payload["planarity_before"], 0.0)
        self.assertAlmostEqual(payload["planarity_after"], 0.0)
        self.assertTrue(all(abs(vertex[2] - 3.0) <= 1e-12 for vertex in payload["optimized_vertices"]))

    def test_summarize_single_primitive_preview_input_reports_l_shaped_residual(self):
        vertices_world = np.array(
            [
                [0.0, 0.0, 0.0],
                [2.0, 0.0, 0.0],
                [4.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [2.0, 1.0, 0.0],
                [4.0, 1.0, 0.0],
                [0.0, 2.0, 0.0],
                [2.0, 2.0, 0.0],
            ]
        )
        faces = (
            (0, 1, 4, 3),
            (1, 2, 5, 4),
            (3, 4, 7, 6),
        )

        summary = summarize_single_primitive_preview_input(vertices_world, faces)

        self.assertIn("raw_outline_vertices=8", summary)
        self.assertIn("primitive_kind=residual", summary)

    def test_generate_primal_graph_from_boundary_roles_accepts_oblique_quad_gable(self):
        vertices_2d = np.array(
            [
                [0.0, 0.0],
                [4.0, 0.0],
                [5.0, 2.0],
                [1.0, 2.0],
            ]
        )

        resolved_vertices, resolved_faces = generate_primal_graph_from_boundary_roles(
            vertices_2d,
            ((0, 1, 2, 3),),
            {
                (0, 1): ROOF_ROLE_EAVE,
                (1, 2): ROOF_ROLE_GABLE_END,
                (2, 3): ROOF_ROLE_EAVE,
                (0, 3): ROOF_ROLE_GABLE_END,
            },
        )

        self.assertEqual(resolved_vertices.shape, (6, 2))
        np.testing.assert_allclose(resolved_vertices[4], np.array([4.5, 1.0]))
        np.testing.assert_allclose(resolved_vertices[5], np.array([0.5, 1.0]))

    def test_generate_primal_graph_from_boundary_roles_accepts_gridded_rectangle_outline(self):
        vertices_2d = np.array(
            [
                [0.0, 0.0],
                [2.0, 0.0],
                [4.0, 0.0],
                [0.0, 1.0],
                [2.0, 1.0],
                [4.0, 1.0],
                [0.0, 2.0],
                [2.0, 2.0],
                [4.0, 2.0],
            ]
        )
        mesh_faces = (
            (0, 1, 4, 3),
            (1, 2, 5, 4),
            (3, 4, 7, 6),
            (4, 5, 8, 7),
        )

        resolved_vertices, resolved_faces = generate_primal_graph_from_boundary_roles(
            vertices_2d,
            mesh_faces,
            {
                (0, 1): ROOF_ROLE_EAVE,
                (1, 2): ROOF_ROLE_EAVE,
                (2, 5): ROOF_ROLE_GABLE_END,
                (5, 8): ROOF_ROLE_GABLE_END,
                (7, 8): ROOF_ROLE_EAVE,
                (6, 7): ROOF_ROLE_EAVE,
                (3, 6): ROOF_ROLE_GABLE_END,
                (0, 3): ROOF_ROLE_GABLE_END,
            },
        )

        self.assertEqual(resolved_vertices.shape, (6, 2))
        self.assertEqual(
            _canonicalize_faces(resolved_faces),
            _canonicalize_faces(((2, 3, 5, 4), (4, 5, 0, 1), (1, 4, 2), (3, 5, 0))),
        )

    def test_resolve_planar_mesh_input_prefers_explicit_primal_faces_over_boundary_roles(self):
        vertices_2d = np.array(
            [
                [0.0, 0.0],
                [4.0, 0.0],
                [4.0, 2.0],
                [0.0, 2.0],
                [2.0, 1.0],
            ]
        )
        explicit_faces = ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4))

        resolved_vertices, resolved_faces = resolve_planar_mesh_input(
            vertices_2d,
            ((0, 1, 2, 3),),
            primal_faces=explicit_faces,
            boundary_edge_roles={(0, 1): ROOF_ROLE_NONE},
        )

        self.assertEqual(resolved_vertices.shape, (5, 2))
        self.assertEqual(resolved_faces, explicit_faces)

    def test_resolve_planar_mesh_input_falls_back_to_boundary_roles_when_explicit_faces_are_boundary_only(self):
        vertices_2d = np.array(
            [
                [0.0, 0.0],
                [2.0, 0.0],
                [4.0, 0.0],
                [0.0, 1.0],
                [2.0, 1.0],
                [4.0, 1.0],
                [0.0, 2.0],
                [2.0, 2.0],
                [4.0, 2.0],
            ]
        )
        mesh_faces = (
            (0, 1, 4, 3),
            (1, 2, 5, 4),
            (3, 4, 7, 6),
            (4, 5, 8, 7),
        )

        resolved_vertices, resolved_faces = resolve_planar_mesh_input(
            vertices_2d,
            mesh_faces,
            primal_faces=((0, 1, 2, 5, 8, 7, 6, 3),),
            boundary_edge_roles={
                (0, 1): ROOF_ROLE_EAVE,
                (1, 2): ROOF_ROLE_EAVE,
                (2, 5): ROOF_ROLE_GABLE_END,
                (5, 8): ROOF_ROLE_GABLE_END,
                (7, 8): ROOF_ROLE_EAVE,
                (6, 7): ROOF_ROLE_EAVE,
                (3, 6): ROOF_ROLE_GABLE_END,
                (0, 3): ROOF_ROLE_GABLE_END,
            },
        )

        self.assertEqual(resolved_vertices.shape, (6, 2))
        self.assertEqual(
            _canonicalize_faces(resolved_faces),
            _canonicalize_faces(((2, 3, 5, 4), (4, 5, 0, 1), (1, 4, 2), (3, 5, 0))),
        )

    def test_solve_primal_roof_graph_returns_serializable_result(self):
        vertices_2d = np.array(
            [
                [0.0, 0.0],
                [1.0, 0.0],
                [1.0, 1.0],
                [0.0, 1.0],
                [0.5, 0.5],
            ]
        )
        faces = ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4))

        result = solve_primal_roof_graph(vertices_2d, faces, roof_height=10.0, lambda_weight=0.0)
        payload = result.to_json_dict()

        self.assertTrue(result.optimizer_success)
        self.assertLessEqual(result.planarity_after, result.planarity_before + 1e-12)
        self.assertEqual(payload["fixed_roof_vertex_id"], 4)
        self.assertEqual(len(payload["optimized_vertices"]), 5)
        json.dumps(payload)

    def test_solve_dual_roof_graph_runs_end_to_end_on_authored_hip(self):
        base_path = Path(__file__).resolve().parent / "fixtures" / "authored_hip" / "sample"
        outline_vertices, adjacency = read_dual_roof_graph(base_path)

        result = solve_dual_roof_graph(outline_vertices, adjacency, roof_height=25.0, lambda_weight=0.1)

        self.assertEqual(len(result.faces), 4)
        self.assertEqual(len(result.optimized_vertices), 6)
        self.assertLessEqual(result.planarity_after, result.planarity_before + 1e-10)
        json.dumps(result.to_json_dict())

    def test_load_roof_result_json_validates_and_normalizes_payload(self):
        payload = {
            "initial_vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 1]],
            "optimized_vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.2], [0.0, 1.0, 1.0]],
            "faces": [[0, 1, 2]],
            "fixed_roof_vertex_id": 2,
            "planarity_before": 1.5,
            "planarity_after": 0.5,
            "optimizer_success": True,
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "result.json"
            json_path.write_text(json.dumps(payload), encoding="utf-8")

            normalized = load_roof_result_json(json_path)

        self.assertEqual(normalized["faces"], ((0, 1, 2),))
        self.assertEqual(normalized["fixed_roof_vertex_id"], 2)
        self.assertTrue(normalized["optimizer_success"])
        self.assertEqual(summarize_result(normalized), "planarity_before=1.500000, planarity_after=0.500000, success=True")

    def test_build_comparison_mesh_specs_offsets_initial_and_optimized_meshes(self):
        payload = {
            "initial_vertices": ((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (0.0, 1.0, 1.0)),
            "optimized_vertices": ((0.0, 0.0, 0.0), (4.0, 0.0, 0.5), (0.0, 1.0, 1.0)),
            "faces": ((0, 1, 2),),
            "fixed_roof_vertex_id": 2,
            "planarity_before": 1.0,
            "planarity_after": 0.5,
            "optimizer_success": True,
        }

        initial_spec, optimized_spec = build_comparison_mesh_specs(payload, mesh_name="demo", separation_factor=1.5)

        self.assertEqual(initial_spec.name, "demo_initial")
        self.assertEqual(optimized_spec.name, "demo_optimized")
        self.assertEqual(initial_spec.location, (-6.0, 0.0, 0.0))
        self.assertEqual(optimized_spec.location, (6.0, 0.0, 0.0))

    def test_solve_primal_graph_to_mesh_specs_uses_existing_sample(self):
        base_path = Path(__file__).resolve().parent / "fixtures" / "authored_hip" / "sample"

        mesh_specs, payload = solve_primal_graph_to_mesh_specs(
            base_path,
            mesh_name="sample",
            roof_height=25.0,
            lambda_weight=0.1,
            separation_factor=1.0,
        )

        self.assertEqual(len(mesh_specs), 2)
        self.assertEqual(mesh_specs[0].name, "sample_initial")
        self.assertEqual(mesh_specs[1].name, "sample_optimized")
        self.assertEqual(len(mesh_specs[0].vertices), len(payload["initial_vertices"]))
        self.assertEqual(len(mesh_specs[0].faces), len(payload["faces"]))
        self.assertLessEqual(payload["planarity_after"], payload["planarity_before"] + 1e-10)

    def test_project_planar_mesh_to_primal_and_lift_round_trip_on_tilted_plane(self):
        vertices_world = np.array(
            [
                [0.0, 0.0, 0.0],
                [2.0, 0.0, 0.0],
                [2.0, 1.0, 1.0],
                [0.0, 1.0, 1.0],
                [1.0, 0.5, 0.5],
            ]
        )
        faces = ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4))

        vertices_2d, normalized_faces, frame = project_planar_mesh_to_primal(vertices_world, faces)
        local_vertices = np.column_stack([vertices_2d, np.zeros(len(vertices_2d))])
        lifted_vertices = np.asarray(lift_local_vertices_to_world(local_vertices, frame))

        self.assertEqual(normalized_faces, faces)
        np.testing.assert_allclose(lifted_vertices, vertices_world, atol=1e-8)

    def test_solve_planar_mesh_to_mesh_specs_returns_world_space_meshes(self):
        vertices_world = np.array(
            [
                [0.0, 0.0, 0.0],
                [2.0, 0.0, 0.0],
                [2.0, 1.0, 1.0],
                [0.0, 1.0, 1.0],
                [1.0, 0.5, 0.5],
            ]
        )
        faces = ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4))

        mesh_specs, payload, frame = solve_planar_mesh_to_mesh_specs(
            vertices_world,
            faces,
            mesh_name="tilted",
            roof_height=3.0,
            lambda_weight=0.0,
            separation_factor=1.0,
        )

        self.assertEqual(mesh_specs[0].name, "tilted_initial")
        self.assertEqual(mesh_specs[1].name, "tilted_optimized")
        self.assertEqual(frame.origin, (0.0, 0.0, 0.0))
        self.assertEqual(len(payload["optimized_vertices"]), 5)
        self.assertLessEqual(payload["planarity_after"], payload["planarity_before"] + 1e-10)

    def test_ensure_roof_vertex_primal_graph_keeps_existing_roof_graph(self):
        vertices_2d = np.array(
            [
                [0.0, 0.0],
                [2.0, 0.0],
                [2.0, 2.0],
                [0.0, 2.0],
                [1.0, 1.0],
            ]
        )
        faces = ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4))

        new_vertices, new_faces = ensure_roof_vertex_primal_graph(vertices_2d, faces)

        self.assertEqual(new_vertices.shape, (5, 2))
        self.assertEqual(new_faces, faces)

    def test_ensure_roof_vertex_primal_graph_rejects_boundary_only_face(self):
        vertices_2d = np.array(
            [
                [0.0, 0.0],
                [4.0, 0.0],
                [4.0, 2.0],
                [0.0, 2.0],
            ]
        )

        with self.assertRaisesRegex(ValueError, "already encode a roof graph"):
            ensure_roof_vertex_primal_graph(vertices_2d, ((0, 1, 2, 3),))

    def test_decode_primal_graph_faces_accepts_json_string(self):
        faces = decode_primal_graph_faces("[[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]]")

        self.assertEqual(faces, ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)))

    def test_encode_and_store_primal_graph_faces_round_trip(self):
        target = {}
        faces = ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4))

        stored_faces = store_primal_graph_faces(target, faces)

        self.assertEqual(stored_faces, faces)
        self.assertEqual(decode_primal_graph_faces(target["roof_graph_faces"]), faces)
        self.assertEqual(encode_primal_graph_faces(faces), target["roof_graph_faces"])

    def test_extract_polygon_faces_can_filter_selected_polygons(self):
        class _Polygon:
            def __init__(self, vertices, select):
                self.vertices = vertices
                self.select = select

        class _Mesh:
            def __init__(self, polygons):
                self.polygons = polygons

        mesh = _Mesh([
            _Polygon((0, 1, 4), False),
            _Polygon((1, 2, 4), True),
            _Polygon((2, 3, 4), True),
        ])

        faces = extract_polygon_faces(mesh, selected_only=True)

        self.assertEqual(faces, ((1, 2, 4), (2, 3, 4)))

    def test_store_roof_graph_metadata_writes_faces_and_solver_config(self):
        target = {}

        stored_faces = store_roof_graph_metadata(
            target,
            ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)),
            {
                "mesh_name": "meta",
                "roof_height": 7.0,
                "lambda_weight": 0.4,
                "fixed_roof_vertex_id": 4,
                "separation_factor": 1.5,
            },
        )

        self.assertEqual(stored_faces, ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)))
        self.assertEqual(decode_primal_graph_faces(target["roof_graph_faces"]), stored_faces)
        self.assertEqual(decode_solver_config(target["roof_solver_config"])["mesh_name"], "meta")

    def test_store_solver_config_round_trip(self):
        target = {}

        stored_config = store_solver_config(
            target,
            {
                "mesh_name": "demo",
                "roof_height": 12.5,
                "lambda_weight": 0.2,
                "fixed_roof_vertex_id": 8,
                "separation_factor": 2.0,
            },
        )

        self.assertEqual(stored_config["mesh_name"], "demo")
        self.assertEqual(stored_config["fixed_roof_vertex_id"], 8)
        self.assertEqual(decode_solver_config(target["roof_solver_config"]), stored_config)
        self.assertEqual(encode_solver_config(stored_config), target["roof_solver_config"])

    def test_read_solver_config_prefers_object_then_mesh(self):
        class _Mesh(dict):
            pass

        class _Object(dict):
            def __init__(self, mesh):
                super().__init__()
                self.data = mesh

        mesh = _Mesh()
        mesh["roof_solver_config"] = '{"mesh_name": "mesh_value", "roof_height": 9.0}'
        obj = _Object(mesh)
        obj["roof_solver_config"] = '{"mesh_name": "object_value", "roof_height": 11.0}'

        self.assertEqual(read_solver_config(obj)["mesh_name"], "object_value")
        del obj["roof_solver_config"]
        self.assertEqual(read_solver_config(obj)["mesh_name"], "mesh_value")

    def test_resolve_solver_config_applies_defaults_stored_and_overrides(self):
        resolved = resolve_solver_config(
            overrides={"mesh_name": "cli_name", "lambda_weight": 0.3},
            stored_config={"mesh_name": "stored_name", "roof_height": 15.0, "fixed_roof_vertex_id": 9},
        )

        self.assertEqual(resolved["mesh_name"], "cli_name")
        self.assertEqual(resolved["roof_height"], 15.0)
        self.assertEqual(resolved["lambda_weight"], 0.3)
        self.assertEqual(resolved["fixed_roof_vertex_id"], 9)
        self.assertEqual(resolved["separation_factor"], 1.25)

    def test_resolve_primal_graph_faces_prefers_explicit_faces(self):
        mesh_faces = ((0, 1, 2, 3),)
        explicit_faces = ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4))

        resolved_faces = resolve_primal_graph_faces(mesh_faces, explicit_faces)

        self.assertEqual(resolved_faces, explicit_faces)

    def test_solve_planar_mesh_to_mesh_specs_rejects_boundary_only_face(self):
        vertices_world = np.array(
            [
                [0.0, 0.0, 0.0],
                [4.0, 0.0, 0.0],
                [4.0, 2.0, 0.0],
                [0.0, 2.0, 0.0],
            ]
        )

        with self.assertRaisesRegex(ValueError, "already encode a roof graph"):
            solve_planar_mesh_to_mesh_specs(
                vertices_world,
                ((0, 1, 2, 3),),
                mesh_name="gable",
                roof_height=3.0,
                lambda_weight=0.0,
                separation_factor=1.0,
            )

    def test_solve_planar_mesh_to_mesh_specs_accepts_explicit_primal_faces_on_boundary_mesh(self):
        vertices_world = np.array(
            [
                [0.0, 0.0, 0.0],
                [4.0, 0.0, 0.0],
                [4.0, 2.0, 0.0],
                [0.0, 2.0, 0.0],
                [2.0, 1.0, 0.0],
            ]
        )
        mesh_faces = ((0, 1, 2, 3),)
        primal_faces = ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4))

        mesh_specs, payload, _frame = solve_planar_mesh_to_mesh_specs(
            vertices_world,
            mesh_faces,
            primal_faces=primal_faces,
            mesh_name="explicit_graph",
            roof_height=3.0,
            lambda_weight=0.0,
            separation_factor=1.0,
        )

        self.assertEqual(len(mesh_specs), 2)
        self.assertEqual(len(payload["faces"]), 4)
        self.assertEqual(len(payload["optimized_vertices"]), 5)
        self.assertLessEqual(payload["planarity_after"], payload["planarity_before"] + 1e-12)

    def test_solve_planar_mesh_to_mesh_specs_accepts_boundary_edge_roles_on_rectangle(self):
        vertices_world = np.array(
            [
                [0.0, 0.0, 0.0],
                [4.0, 0.0, 0.0],
                [4.0, 2.0, 0.0],
                [0.0, 2.0, 0.0],
            ]
        )

        mesh_specs, payload, _frame = solve_planar_mesh_to_mesh_specs(
            vertices_world,
            ((0, 1, 2, 3),),
            boundary_edge_roles={
                (0, 1): ROOF_ROLE_EAVE,
                (1, 2): ROOF_ROLE_GABLE_END,
                (2, 3): ROOF_ROLE_EAVE,
                (0, 3): ROOF_ROLE_GABLE_END,
            },
            mesh_name="boundary_roles",
            roof_height=3.0,
            lambda_weight=0.0,
            separation_factor=1.0,
        )

        self.assertEqual(len(mesh_specs), 2)
        self.assertEqual(len(payload["faces"]), 4)
        self.assertEqual(len(payload["optimized_vertices"]), 6)
        self.assertEqual(mesh_specs[0].face_int_attributes["roof_region_i"], (0, 0, 0, 0))
        self.assertLessEqual(payload["planarity_after"], payload["planarity_before"] + 1e-12)

        topology = build_roof_graph_topology(np.asarray(mesh_specs[0].vertices, dtype=float), mesh_specs[0].faces)
        observed_roles = {
            topology.edges[edge_id]: mesh_specs[0].edge_int_attributes["roof_role_i"][edge_id]
            for edge_id in topology.outline_edge_ids
        }
        self.assertEqual(observed_roles[(0, 1)], ROOF_ROLE_EAVE)
        self.assertEqual(observed_roles[(1, 2)], ROOF_ROLE_GABLE_END)
        self.assertEqual(observed_roles[(2, 3)], ROOF_ROLE_EAVE)
        self.assertEqual(observed_roles[(0, 3)], ROOF_ROLE_GABLE_END)

    def test_solve_planar_mesh_to_mesh_specs_accepts_boundary_edge_roles_on_gridded_rectangle(self):
        vertices_world = np.array(
            [
                [0.0, 0.0, 0.0],
                [2.0, 0.0, 0.0],
                [4.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [2.0, 1.0, 0.0],
                [4.0, 1.0, 0.0],
                [0.0, 2.0, 0.0],
                [2.0, 2.0, 0.0],
                [4.0, 2.0, 0.0],
            ]
        )
        mesh_faces = (
            (0, 1, 4, 3),
            (1, 2, 5, 4),
            (3, 4, 7, 6),
            (4, 5, 8, 7),
        )

        mesh_specs, payload, _frame = solve_planar_mesh_to_mesh_specs(
            vertices_world,
            mesh_faces,
            boundary_edge_roles={
                (0, 1): ROOF_ROLE_EAVE,
                (1, 2): ROOF_ROLE_EAVE,
                (2, 5): ROOF_ROLE_GABLE_END,
                (5, 8): ROOF_ROLE_GABLE_END,
                (7, 8): ROOF_ROLE_EAVE,
                (6, 7): ROOF_ROLE_EAVE,
                (3, 6): ROOF_ROLE_GABLE_END,
                (0, 3): ROOF_ROLE_GABLE_END,
            },
            mesh_name="grid_boundary_roles",
            roof_height=3.0,
            lambda_weight=0.0,
            separation_factor=1.0,
        )

        self.assertEqual(len(mesh_specs), 2)
        self.assertEqual(len(payload["faces"]), 4)
        self.assertEqual(len(payload["optimized_vertices"]), 6)
        self.assertLessEqual(payload["planarity_after"], payload["planarity_before"] + 1e-12)

    def test_build_mesh_attribute_payload_marks_outline_edges_for_boundary_roles(self):
        payload = {
            "initial_vertices": ((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 2.0, 0.0), (0.0, 2.0, 0.0), (4.0, 1.0, 3.0), (0.0, 1.0, 3.0)),
            "optimized_vertices": ((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 2.0, 0.0), (0.0, 2.0, 0.0), (4.0, 1.0, 3.0), (0.0, 1.0, 3.0)),
            "faces": ((2, 3, 5, 4), (4, 5, 0, 1), (1, 4, 2), (3, 5, 0)),
        }

        edge_int_attributes, edge_float_attributes, face_int_attributes = build_mesh_attribute_payload(
            payload,
            boundary_edge_roles={(0, 1): ROOF_ROLE_EAVE, (1, 2): ROOF_ROLE_GABLE_END, (2, 3): ROOF_ROLE_EAVE, (0, 3): ROOF_ROLE_GABLE_END},
            roof_height=3.0,
        )

        topology = build_roof_graph_topology(np.asarray(payload["initial_vertices"], dtype=float), payload["faces"])
        observed_roles = {
            topology.edges[edge_id]: edge_int_attributes["roof_role_i"][edge_id]
            for edge_id in topology.outline_edge_ids
        }
        self.assertEqual(observed_roles, {(0, 1): 1, (1, 2): 2, (2, 3): 1, (0, 3): 2})
        self.assertTrue(all(edge_float_attributes["roof_height"][edge_id] == 3.0 for edge_id in topology.outline_edge_ids))
        self.assertEqual(face_int_attributes["roof_region_i"], (0, 0, 0, 0))

    def test_extract_boundary_edge_roles_reads_roof_role_attribute(self):
        class _Edge:
            def __init__(self, index, vertices):
                self.index = index
                self.vertices = vertices

        class _AttributeValue:
            def __init__(self, value):
                self.value = value

        class _Attribute:
            def __init__(self, values):
                self.data = [_AttributeValue(value) for value in values]

        class _Attributes(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        class _Mesh(dict):
            def __init__(self):
                super().__init__()
                self.edges = [
                    _Edge(0, (0, 1)),
                    _Edge(1, (1, 2)),
                    _Edge(2, (2, 3)),
                    _Edge(3, (3, 0)),
                ]
                self.attributes = _Attributes({"roof_role_i": _Attribute([1, 2, 0, 2])})

        class _Object(dict):
            def __init__(self, mesh):
                super().__init__()
                self.data = mesh

        edge_roles = extract_boundary_edge_roles(_Object(_Mesh()))

        self.assertEqual(edge_roles, {(0, 1): 1, (1, 2): 2, (0, 3): 2})

    def test_roof_role_props_store_read_clear_and_summarize(self):
        class _Edge:
            def __init__(self, index, select=False):
                self.index = index
                self.select = select

        class _AttributeValue:
            def __init__(self):
                self.value = 0

        class _Attribute:
            def __init__(self, size):
                self.data = [_AttributeValue() for _ in range(size)]

        class _Attributes(dict):
            def __init__(self, mesh):
                super().__init__()
                self._mesh = mesh

            def get(self, key, default=None):
                return super().get(key, default)

            def new(self, name, type, domain):
                self[name] = _Attribute(len(self._mesh.edges))
                return self[name]

        class _Mesh:
            def __init__(self):
                self.edges = [_Edge(0, False), _Edge(1, True), _Edge(2, True), _Edge(3, False)]
                self.attributes = _Attributes(self)

        mesh = _Mesh()

        stored = store_roof_edge_roles(mesh, {0: "eave", 3: 2})
        self.assertEqual(stored, {0: 1, 3: 2})
        self.assertEqual(read_roof_edge_roles(mesh), {0: 1, 3: 2})
        self.assertEqual(normalize_roof_role_code("shed_high"), 4)

        role_code, selected = set_selected_roof_edge_role(mesh, "gable_end")
        self.assertEqual(role_code, 2)
        self.assertEqual(selected, {1: 2, 2: 2})
        self.assertEqual(read_roof_edge_roles(mesh), {0: 1, 1: 2, 2: 2, 3: 2})
        self.assertIn("nonzero_edges=4", summarize_roof_edge_roles(mesh))

        cleared_count = clear_roof_edge_roles(mesh)
        self.assertEqual(cleared_count, 4)
        self.assertEqual(read_roof_edge_roles(mesh), {})

    def test_set_selected_roof_edge_role_rejects_empty_selection(self):
        class _Edge:
            def __init__(self, index, select=False):
                self.index = index
                self.select = select

        class _AttributeValue:
            def __init__(self):
                self.value = 0

        class _Attribute:
            def __init__(self, size):
                self.data = [_AttributeValue() for _ in range(size)]

        class _Attributes(dict):
            def __init__(self, mesh):
                super().__init__()
                self._mesh = mesh

            def get(self, key, default=None):
                return super().get(key, default)

            def new(self, name, type, domain):
                self[name] = _Attribute(len(self._mesh.edges))
                return self[name]

        class _Mesh:
            def __init__(self):
                self.edges = [_Edge(0, False), _Edge(1, False)]
                self.attributes = _Attributes(self)

        with self.assertRaisesRegex(ValueError, "no selected mesh edges"):
            set_selected_roof_edge_role(_Mesh(), "eave")

    def test_extract_boundary_edge_roles_prefers_evaluated_mesh_when_available(self):
        class _Edge:
            def __init__(self, index, vertices):
                self.index = index
                self.vertices = vertices

        class _AttributeValue:
            def __init__(self, value):
                self.value = value

        class _Attribute:
            def __init__(self, values):
                self.data = [_AttributeValue(value) for value in values]

        class _Attributes(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        class _Mesh:
            def __init__(self, values):
                self.edges = [
                    _Edge(0, (0, 1)),
                    _Edge(1, (1, 2)),
                    _Edge(2, (2, 3)),
                    _Edge(3, (3, 0)),
                ]
                self.vertices = [object(), object(), object(), object()]
                self.polygons = [object()]
                self.attributes = _Attributes({"roof_role_i": _Attribute(values)})

        class _EvaluatedObject:
            def __init__(self, mesh, matrix_world):
                self._mesh = mesh
                self.matrix_world = matrix_world

            def to_mesh(self, *args, **kwargs):
                return self._mesh

            def to_mesh_clear(self):
                return None

        class _Object(dict):
            def __init__(self, mesh, evaluated_mesh):
                super().__init__()
                self.data = mesh
                self.matrix_world = object()
                self._evaluated = _EvaluatedObject(evaluated_mesh, self.matrix_world)

            def evaluated_get(self, _depsgraph):
                return self._evaluated

        edge_roles = extract_boundary_edge_roles(_Object(_Mesh([0, 0, 0, 0]), _Mesh([1, 2, 0, 2])))

        self.assertEqual(edge_roles, {(0, 1): 1, (1, 2): 2, (0, 3): 2})

    def test_extract_boundary_edge_roles_falls_back_to_original_mesh_when_evaluated_is_missing(self):
        class _Edge:
            def __init__(self, index, vertices):
                self.index = index
                self.vertices = vertices

        class _AttributeValue:
            def __init__(self, value):
                self.value = value

        class _Attribute:
            def __init__(self, values):
                self.data = [_AttributeValue(value) for value in values]

        class _Attributes(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        class _Mesh:
            def __init__(self, values):
                self.edges = [
                    _Edge(0, (0, 1)),
                    _Edge(1, (1, 2)),
                    _Edge(2, (2, 3)),
                    _Edge(3, (3, 0)),
                ]
                self.vertices = [object(), object(), object(), object()]
                self.polygons = [object()]
                self.attributes = _Attributes({"roof_role_i": _Attribute(values)})

        class _EvaluatedObject:
            def __init__(self, mesh, matrix_world):
                self._mesh = mesh
                self.matrix_world = matrix_world

            def to_mesh(self, *args, **kwargs):
                return self._mesh

            def to_mesh_clear(self):
                return None

        class _Object(dict):
            def __init__(self, mesh, evaluated_mesh):
                super().__init__()
                self.data = mesh
                self.matrix_world = object()
                self._evaluated = _EvaluatedObject(evaluated_mesh, self.matrix_world)

            def evaluated_get(self, _depsgraph):
                return self._evaluated

        edge_roles = extract_boundary_edge_roles(_Object(_Mesh([1, 2, 0, 2]), _Mesh([0, 0, 0, 0])))

        self.assertEqual(edge_roles, {(0, 1): 1, (1, 2): 2, (0, 3): 2})

    def test_extract_boundary_edge_roles_with_source_reports_original_fallback(self):
        class _Edge:
            def __init__(self, index, vertices):
                self.index = index
                self.vertices = vertices

        class _AttributeValue:
            def __init__(self, value):
                self.value = value

        class _Attribute:
            def __init__(self, values):
                self.data = [_AttributeValue(value) for value in values]

        class _Attributes(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        class _Mesh:
            def __init__(self, values):
                self.edges = [_Edge(0, (0, 1)), _Edge(1, (1, 2)), _Edge(2, (2, 3)), _Edge(3, (3, 0))]
                self.vertices = [object(), object(), object(), object()]
                self.polygons = [object()]
                self.attributes = _Attributes({"roof_role_i": _Attribute(values)})

        class _EvaluatedObject:
            def __init__(self, mesh, matrix_world):
                self._mesh = mesh
                self.matrix_world = matrix_world

            def to_mesh(self, *args, **kwargs):
                return self._mesh

            def to_mesh_clear(self):
                return None

        class _Object(dict):
            def __init__(self, mesh, evaluated_mesh):
                super().__init__()
                self.data = mesh
                self.matrix_world = object()
                self._evaluated = _EvaluatedObject(evaluated_mesh, self.matrix_world)

            def evaluated_get(self, _depsgraph):
                return self._evaluated

        edge_roles, role_source = extract_boundary_edge_roles_with_source(_Object(_Mesh([1, 2, 0, 2]), _Mesh([0, 0, 0, 0])))

        self.assertEqual(edge_roles, {(0, 1): 1, (1, 2): 2, (0, 3): 2})
        self.assertEqual(role_source, "original-fallback")

    def test_describe_mesh_input_reports_role_availability(self):
        class _Edge:
            def __init__(self, index, vertices):
                self.index = index
                self.vertices = vertices

        class _AttributeValue:
            def __init__(self, value):
                self.value = value

        class _Attribute:
            def __init__(self, values):
                self.data = [_AttributeValue(value) for value in values]

        class _Attributes(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        class _Mesh:
            def __init__(self):
                self.edges = [_Edge(0, (0, 1)), _Edge(1, (1, 2)), _Edge(2, (2, 3)), _Edge(3, (3, 0))]
                self.vertices = [object(), object(), object(), object()]
                self.polygons = [object()]
                self.attributes = _Attributes({"roof_role_i": _Attribute([1, 2, 0, 2])})

        class _Object(dict):
            def __init__(self, mesh):
                super().__init__()
                self.data = mesh
                self.matrix_world = object()

        summary = describe_mesh_input(_Object(_Mesh()))

        self.assertIn("mesh_source=original", summary)
        self.assertIn("evaluated_roof_role_i=present", summary)
        self.assertIn("original_roof_role_i=present", summary)
        self.assertIn("selected_role_source=original", summary)
        self.assertIn("selected_nonzero_role_edges=3", summary)

    def test_describe_mesh_input_handles_evaluated_mesh_cleanup_during_role_source_resolution(self):
        class _Edge:
            def __init__(self, index, vertices):
                self.index = index
                self.vertices = vertices

        class _AttributeValue:
            def __init__(self, value):
                self.value = value

        class _Attribute:
            def __init__(self, values):
                self.data = [_AttributeValue(value) for value in values]

        class _Attributes(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        class _Mesh:
            def __init__(self, values):
                self._alive = True
                self.edges = [_Edge(0, (0, 1)), _Edge(1, (1, 2)), _Edge(2, (2, 3)), _Edge(3, (3, 0))]
                self._vertices = [object(), object(), object(), object()]
                self._polygons = [object()]
                self.attributes = _Attributes({"roof_role_i": _Attribute(values)})

            @property
            def vertices(self):
                if not self._alive:
                    raise ReferenceError("StructRNA of type Mesh has been removed")
                return self._vertices

            @property
            def polygons(self):
                if not self._alive:
                    raise ReferenceError("StructRNA of type Mesh has been removed")
                return self._polygons

            def invalidate(self):
                self._alive = False

        class _EvaluatedObject:
            def __init__(self, mesh, matrix_world):
                self._mesh = mesh
                self.matrix_world = matrix_world

            def to_mesh(self, *args, **kwargs):
                return self._mesh

            def to_mesh_clear(self):
                self._mesh.invalidate()

        class _Object(dict):
            def __init__(self, mesh, evaluated_mesh):
                super().__init__()
                self.data = mesh
                self.matrix_world = object()
                self._evaluated = _EvaluatedObject(evaluated_mesh, self.matrix_world)

            def evaluated_get(self, _depsgraph):
                return self._evaluated

        summary = describe_mesh_input(_Object(_Mesh([1, 2, 0, 2]), _Mesh([0, 0, 0, 0])))

        self.assertIn("mesh_source=evaluated", summary)
        self.assertIn("selected_role_source=original-fallback", summary)

    def test_write_mesh_spec_attributes_writes_edge_and_face_domains(self):
        class _AttributeValue:
            def __init__(self):
                self.value = None

        class _Attribute:
            def __init__(self, name, data_type, domain, size):
                self.name = name
                self.data_type = data_type
                self.domain = domain
                self.data = [_AttributeValue() for _ in range(size)]

        class _Attributes(dict):
            def __init__(self, mesh):
                super().__init__()
                self._mesh = mesh

            def new(self, name, type, domain):
                size = len(self._mesh.edges) if domain == "EDGE" else len(self._mesh.polygons)
                attribute = _Attribute(name, type, domain, size)
                self[name] = attribute
                return attribute

        class _Mesh:
            def __init__(self):
                self.edges = [object(), object(), object(), object(), object(), object(), object(), object()]
                self.polygons = [object(), object(), object(), object()]
                self.attributes = _Attributes(self)

        mesh_spec = MeshSpec(
            name="demo",
            vertices=((0.0, 0.0, 0.0),),
            faces=((0, 0, 0),),
            location=(0.0, 0.0, 0.0),
            color=(1.0, 1.0, 1.0, 1.0),
            edge_int_attributes={"roof_role_i": (1, 2, 1, 2, 0, 0, 0, 0)},
            edge_float_attributes={"roof_height": (3.0, 3.0, 3.0, 3.0, 0.0, 0.0, 0.0, 0.0)},
            face_int_attributes={"roof_region_i": (0, 0, 0, 0)},
        )

        mesh = _Mesh()
        write_mesh_spec_attributes(mesh, mesh_spec)

        self.assertEqual([value.value for value in mesh.attributes["roof_role_i"].data], [1, 2, 1, 2, 0, 0, 0, 0])
        self.assertEqual([value.value for value in mesh.attributes["roof_height"].data], [3.0, 3.0, 3.0, 3.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual([value.value for value in mesh.attributes["roof_region_i"].data], [0, 0, 0, 0])

    def test_solve_planar_mesh_to_mesh_specs_keeps_existing_roof_graph_without_sharp_inference(self):
        vertices_world = np.array(
            [
                [0.0, 0.0, 0.0],
                [2.0, 0.0, 0.0],
                [4.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [2.0, 1.0, 0.0],
                [4.0, 1.0, 0.0],
                [0.0, 2.0, 0.0],
                [2.0, 2.0, 0.0],
                [4.0, 2.0, 0.0],
            ]
        )
        faces = (
            (0, 1, 4, 3),
            (1, 2, 5, 4),
            (3, 4, 7, 6),
            (4, 5, 8, 7),
        )

        mesh_specs, payload, _frame = solve_planar_mesh_to_mesh_specs(
            vertices_world,
            faces,
            mesh_name="gable_grid",
            roof_height=3.0,
            lambda_weight=0.0,
            separation_factor=1.0,
        )

        self.assertEqual(len(payload["optimized_vertices"]), 9)
        self.assertEqual(len(payload["faces"]), 4)
        self.assertEqual(mesh_specs[0].name, "gable_grid_initial")
        self.assertLessEqual(payload["planarity_after"], payload["planarity_before"] + 1e-12)

if __name__ == "__main__":
    unittest.main()


def _canonicalize_faces(faces):
    canonical_faces = []
    for face in faces:
        face = tuple(int(vertex_id) for vertex_id in face)
        rotations = [face[index:] + face[:index] for index in range(len(face))]
        reversed_face = tuple(reversed(face))
        rotations.extend(reversed_face[index:] + reversed_face[:index] for index in range(len(reversed_face)))
        canonical_faces.append(min(rotations))
    return tuple(sorted(canonical_faces))
