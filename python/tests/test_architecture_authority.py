# SPDX-License-Identifier: GPL-3.0-or-later
"""Authority witnesses independent of the composer's member-port recognition."""

import unittest
from unittest.mock import patch
import python
from roof_generator.core.generation import prepare_generation
from roof_generator.core import topology_candidates
from roof_generator.core import topology
from roof_generator.core import polygon_generation
from roof_generator.core.polygon_roof import PolygonRoof
from roof_generator.core.solve import solve
from roof_generator.core.errors import UnsupportedRoofError
from dataclasses import replace


class ArchitectureAuthorityProof(unittest.TestCase):
    def test_composer_receives_architecture_not_a_decomposition(self):
        received = []
        original = polygon_generation.topology

        def observe(authority, *args, **kwargs):
            received.append(authority)
            return original(authority, *args, **kwargs)

        with patch.object(polygon_generation, "topology", observe):
            prepare_generation(((0, 0), (12, 0), (12, 4), (4, 4), (4, 10), (0, 10)))
        self.assertTrue(received)
        for authority in received:
            self.assertIsInstance(authority,PolygonRoof)
            self.assertTrue(authority.gable_edges)

    def test_compound_never_generates_independent_cell_roofs(self):
        raw = ((0, 0), (12, 0), (12, 4), (4, 4), (4, 10), (0, 10))
        with patch.object(topology, "cell_primitives", side_effect=AssertionError("Cell roof assumption")):
            generation = prepare_generation(raw)
        candidate=generation.selected
        self.assertIsInstance(candidate.architecture,PolygonRoof)
        self.assertEqual(candidate.architecture.footprint,generation.footprint)
        self.assertEqual({f.cells for f in candidate.graph.faces},{(0,)})
        self.assertTrue(candidate.inspect_features())
        self.assertTrue(any(f['kind']=='valley' for f in candidate.inspect_features()))
        for cause in candidate.inspect_features():
            self.assertEqual(cause['region'],0)
            self.assertTrue(all(cause['source_eaves']))

    def test_embedding_preserves_incidence_semantics_and_causes(self):
        raw = ((0, 0), (18, 0), (18, 6), (14, 6), (14, 12), (10, 12), (10, 6), (4, 6), (4, 12), (0, 12))
        candidate = prepare_generation(raw).selected
        graph = candidate.graph
        before = (graph.inspect(), candidate.inspect_features())
        mesh = solve(graph, candidate.geometry)
        self.assertIs(mesh.graph, graph)
        self.assertEqual(before, (mesh.graph.inspect(), candidate.inspect_features()))
        changed=tuple(sorted(set(candidate.architecture.gable_edges)^set((candidate.architecture.gable_edges[0],))))
        with self.assertRaises(UnsupportedRoofError):
            replace(candidate,architecture=replace(candidate.architecture,gable_edges=changed))

    def test_s_mino_is_explicit_unsupported_parallel_for_every_seed(self):
        from roof_generator.core.architecture_selection import recommend
        from roof_generator.core.partition_candidates import candidates
        from roof_generator.core.footprint import analyze
        raw = ((1, 0), (3, 0), (3, 1), (2, 1), (2, 2), (0, 2), (0, 1), (1, 1))
        pool = topology_candidates.build_candidates(recommend(candidates(analyze(raw)), defer_ranking=True))
        self.assertFalse(pool.valid)
        self.assertEqual({i.code for r in pool.rejected for i in r.issues}, {"inter_part_parallel"})
        self.assertTrue(pool.architectural)
        for seed in (0, 1, 42):
            with self.assertRaises(UnsupportedRoofError):
                pool.select(seed)

    def test_architectural_preference_is_independent_of_available_operations(self):
        from roof_generator.core.architecture_selection import recommend
        from roof_generator.core.partition_candidates import candidates
        from roof_generator.core.footprint import analyze
        from python.inspect_architectural_parts import fixture
        interpretation = recommend(candidates(analyze(fixture("cross")["footprint"])), defer_ranking=True)
        normal = topology_candidates.build_candidates(interpretation)
        with patch.object(topology_candidates, "compose", side_effect=UnsupportedRoofError("operation unavailable")):
            unavailable = topology_candidates.build_candidates(interpretation)
        self.assertEqual(normal.architectural, unavailable.architectural)
        self.assertEqual(normal.inspect_ranking()["architectural_preferred_assignments"], unavailable.inspect_ranking()["architectural_preferred_assignments"])
        self.assertTrue(normal.constructible)
        self.assertFalse(unavailable.constructible)
        self.assertFalse(unavailable.valid)


if __name__ == "__main__":
    unittest.main()
