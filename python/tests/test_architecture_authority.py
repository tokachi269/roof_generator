# SPDX-License-Identifier: GPL-3.0-or-later
"""Authority witnesses independent of the composer's member-port recognition."""

import unittest
from unittest.mock import patch
import python
from roof_generator.core.generation import prepare_generation
from roof_generator.core import topology_candidates
from roof_generator.core import topology
from roof_generator.core.solve import solve
from roof_generator.core.errors import UnsupportedRoofError
from dataclasses import replace


class ArchitectureAuthorityProof(unittest.TestCase):
    def test_composer_receives_architecture_not_a_decomposition(self):
        received = []
        original = topology_candidates.compose

        def observe(authority, *args, **kwargs):
            received.append(authority)
            return original(authority, *args, **kwargs)

        with patch.object(topology_candidates, "compose", observe):
            prepare_generation(((0, 0), (12, 0), (12, 4), (4, 4), (4, 10), (0, 10)))
        self.assertTrue(received)
        for authority in received:
            self.assertTrue(hasattr(authority, "architecture"))
            self.assertTrue(hasattr(authority, "relations"))
            self.assertTrue(hasattr(authority, "axes"))

    def test_compound_never_generates_independent_cell_roofs(self):
        raw = ((0, 0), (12, 0), (12, 4), (4, 4), (4, 10), (0, 10))
        with patch.object(topology, "cell_primitives", side_effect=AssertionError("Cell roof assumption")):
            generation = prepare_generation(raw)
        candidate = generation.selected
        composition = candidate.composition
        self.assertEqual(composition.primitives, ())
        self.assertEqual(len(candidate.architecture.parts), 1)
        self.assertEqual(len(candidate.architecture.parts[0].cells), 2)
        self.assertTrue(composition.connections)
        for cause in composition.features:
            self.assertEqual(cause.parts, (0,))
            if cause.kind in {"hip", "valley"}:
                self.assertEqual(cause.relation, (0, 1))
                self.assertEqual(cause.operation, "terminal")
        # Preserve the existing terminal template's geometric regression.
        # This is not proof that architecture should adopt this junction:
        # Part grouping and feature provenance do not establish roof intent.
        self.assertTrue(any(f.kind == "valley" for f in composition.features))

    def test_embedding_preserves_incidence_semantics_and_causes(self):
        raw = ((0, 0), (18, 0), (18, 6), (14, 6), (14, 12), (10, 12), (10, 6), (4, 6), (4, 12), (0, 12))
        candidate = prepare_generation(raw).selected
        graph = candidate.graph
        before = (graph.inspect(), candidate.composition.features)
        mesh = solve(graph, candidate.geometry)
        self.assertIs(mesh.graph, graph)
        self.assertEqual(before, (mesh.graph.inspect(), candidate.composition.features))
        cause = candidate.composition.features[0]
        with self.assertRaises(UnsupportedRoofError):
            replace(candidate.composition, features=(replace(cause, kind="eave"),) + candidate.composition.features[1:])

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
