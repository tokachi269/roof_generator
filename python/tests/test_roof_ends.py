# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
import python
from roof_generator.core.generation import prepare_generation
from roof_generator.core.roof_ends import End, EndShape, EndChoice, EndRule, configurations, roof_configurations
from roof_generator.core.architecture import interpret, resolve
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose
from roof_generator.core.topology import compose
from roof_generator.core.errors import UnsupportedRoofError


class RoofEndAuthorityProof(unittest.TestCase):
    def test_equal_corner_T_preserves_its_eave_free_face_through_embedding(self):
        from roof_generator.core.solve import problem, solve
        raw = ((0, 0), (12, 0), (12, 4), (4, 4), (4, 10), (0, 10))
        architecture = interpret(decompose(analyze(raw)))
        resolved = resolve(architecture, tuple(m.axes[0] for m in architecture.members))
        ends = next(c for c in roof_configurations(resolved) if c.joints[0].kind == 'extension')
        composition = compose(resolved.with_ends(ends))
        graph = composition.graph
        points = {'A': (0, 0), 'B': (12, 0), 'C': (12, 4), 'D': (4, 4),
                  'E': (4, 10), 'F': (0, 10), 'G': (0, 4),
                  'H': (12, 2), 'I': (0, 2), 'K': (2, 10), 'J': (2, 2)}
        names = {}
        for i, vertex in enumerate(graph.vertices):
            xy = architecture.decomposition.footprint.frame.world_xy(vertex.seed)
            names[i] = next(k for k, p in points.items() if max(abs(a-b) for a,b in zip(xy,p)) < 1e-7)
        canonical = lambda ring: min(tuple(ring[i:] + ring[:i]) for i in range(len(ring)))
        expected = ('ABHJI', 'HCDJ', 'JGI', 'DEKJ', 'KFGJ')
        self.assertEqual({canonical([names[v] for v in f.loop]) for f in graph.faces},
                         {canonical(list(r)) for r in expected})
        internal = [f for f in graph.faces if not f.eaves]
        self.assertEqual(len(internal), 1)
        self.assertIsNotNone(internal[0].support)
        # Removing the upstream declaration must not trigger a guessed slope.
        from dataclasses import replace
        missing = replace(graph, faces=tuple(replace(f, support=None) if not f.eaves else f for f in graph.faces))
        with self.assertRaisesRegex(UnsupportedRoofError, 'declared eave support'):
            problem(missing, .5)
        foreign = next(f.eaves[0] for f in graph.faces if f.eaves and f.cells != internal[0].cells)
        with self.assertRaisesRegex(UnsupportedRoofError, 'declared member'):
            replace(graph, faces=tuple(replace(f, support=foreign) if not f.eaves else f for f in graph.faces))
        before = graph.inspect()
        mesh = solve(graph, problem(graph, .5))
        self.assertIs(mesh.graph, graph)
        self.assertEqual(graph.inspect(), before)
        for i, xyz in enumerate(mesh.vertices):
            world = architecture.decomposition.footprint.frame.world_xyz(xyz)
            target = (*points[names[i]], 1 if names[i] in 'HIJK' else 0)
            self.assertLess(max(abs(a-b) for a,b in zip(world,target)), 1e-5)

    def test_offset_short_end_contact_does_not_receive_one_line_constraints(self):
        raw = ((0, 0), (6, 0), (6, 12), (8, 12), (8, 24), (2, 24), (2, 12), (0, 12))
        architecture = interpret(decompose(analyze(raw)))
        resolved = resolve(architecture, tuple(m.axes[0] for m in architecture.members))
        self.assertEqual(resolved.relations[0].options[0].kind, 'continuation')
        with self.assertRaises(UnsupportedRoofError) as error:
            tuple(roof_configurations(resolved))
        self.assertIn('offset', str(error.exception))
        self.assertTrue(all(issue.code.endswith('offset_continuation') for issue in error.exception.issues))

    def test_selected_compound_has_resolved_end_configuration_before_composition(self):
        roof = prepare_generation(((0, 0), (12, 0), (12, 4), (4, 4), (4, 10), (0, 10)))
        self.assertIsNotNone(getattr(roof.selected, 'ends', None),
                             'Cell contact labels are not a resolved roof end configuration')

    def test_same_end_one_line_constraint_eliminates_shared_L_option(self):
        # Independent Hu Fig.18 constraint witness: one-line forces A's end
        # gabled; the L choice at that same end must consequently be T.
        a, b, c = End(0, 1), End(1, 3), End(2, 3)
        shared = EndChoice((0, 1), 'shared', ((a, EndShape.SHARED), (b, EndShape.SHARED)))
        extension = EndChoice((0, 1), 'extension', ((b, EndShape.GABLE),))
        line = EndChoice((0, 2), 'continuation', ((a, EndShape.GABLE), (c, EndShape.GABLE)))
        rules = (EndRule((0, 1), (shared, extension)), EndRule((0, 2), (line,)))
        result = tuple(configurations((a, b, c), rules))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].joints, (extension, line))
        self.assertEqual(result, tuple(configurations((c, a, b), tuple(reversed(rules)))))

    def test_symmetry_constrains_joint_choices_before_topology(self):
        a, b, c, d = (End(i, 1) for i in range(4))
        choices = []
        for x, y in ((a, b), (c, d)):
            cells = (x.member, y.member)
            choices.append(EndRule(cells, (
                EndChoice(cells, 'shared', ((x, EndShape.SHARED), (y, EndShape.SHARED))),
                EndChoice(cells, 'extension', ((y, EndShape.GABLE),)),
            )))
        result = tuple(configurations((a, b, c, d), choices, ((a, c), (b, d))))
        self.assertEqual(len(result), 2)
        self.assertEqual({tuple(j.kind for j in r.joints) for r in result},
                         {('shared', 'shared'), ('extension', 'extension')})

    def test_resolved_T_is_not_silently_reinterpreted_as_shared_terminal(self):
        raw = ((0, 0), (12, 0), (12, 4), (4, 4), (4, 10), (0, 10))
        architecture = interpret(decompose(analyze(raw)))
        resolved = resolve(architecture, tuple(m.axes[0] for m in architecture.members))
        options = tuple(roof_configurations(resolved))
        self.assertEqual({j.kind for c in options for j in c.joints}, {'shared', 'extension'})
        shared = next(c for c in options if c.joints[0].kind == 'shared')
        extended = next(c for c in options if c.joints[0].kind == 'extension')
        self.assertEqual(len(resolved.with_ends(shared).architecture.parts), 1)
        self.assertEqual(len(resolved.with_ends(extended).architecture.parts), 2)
        self.assertTrue(compose(resolved.with_ends(shared)).connections)
        composition = compose(resolved.with_ends(extended))
        self.assertEqual({c.kind for c in composition.connections}, {'middle'})
        self.assertEqual(len(composition.graph.faces), 5)

    def test_wider_corner_T_still_has_no_unproved_extension_fallback(self):
        raw = ((0, 0), (12, 0), (12, 6), (4, 6), (4, 12), (0, 12))
        architecture = interpret(decompose(analyze(raw)))
        resolved = resolve(architecture, tuple(m.axes[0] for m in architecture.members))
        option = resolved.relations[0].options[0]
        self.assertGreater(option.widths[1], option.widths[0])
        ends = next(c for c in roof_configurations(resolved) if c.joints[0].kind == 'extension')
        with self.assertRaises(UnsupportedRoofError) as error:
            compose(resolved.with_ends(ends))
        self.assertEqual({i.code for i in error.exception.issues}, {'corner_extension'})

    def test_narrow_corner_T_has_an_independent_extension_incidence_witness(self):
        raw = ((0, 0), (12, 0), (12, 6), (4, 6), (4, 12), (0, 12))
        from roof_generator.core.partition_candidates import candidates
        architecture = next(a for a in (interpret(d) for d in candidates(analyze(raw)).candidates)
                            if a.relations[0].options[0].widths[1] < a.relations[0].options[0].widths[0])
        resolved = resolve(architecture, tuple(m.axes[0] for m in architecture.members))
        ends = next(c for c in roof_configurations(resolved) if c.joints[0].kind == 'extension')
        composition = compose(resolved.with_ends(ends))
        graph = composition.graph
        # Authored face cycles: A..F are the outline, G the collinear outlet,
        # H/I receiver end ports, K branch end, J its slope termination.
        points = {'A': (0, 0), 'B': (12, 0), 'C': (12, 6), 'D': (4, 6),
                  'E': (4, 12), 'F': (0, 12), 'G': (0, 6),
                  'H': (12, 3), 'I': (0, 3), 'K': (2, 12)}
        names = {}
        for i, vertex in enumerate(graph.vertices):
            if vertex.role == 'junction':
                names[i] = 'J'
            else:
                xy = architecture.decomposition.footprint.frame.world_xy(vertex.seed)
                names[i] = next(k for k, p in points.items() if max(abs(a-b) for a,b in zip(xy,p)) < 1e-7)
        canonical = lambda ring: min(tuple(ring[i:] + ring[:i]) for i in range(len(ring)))
        expected = ('ABHI', 'HCDJGI', 'DEKJ', 'KFGJ')
        self.assertEqual({canonical([names[v] for v in f.loop]) for f in graph.faces},
                         {canonical(list(r)) for r in expected})
        self.assertEqual(sum(e.kind == 'valley' for e in graph.edges), 2)
        self.assertFalse(any(e.kind == 'hip' for e in graph.edges))
        self.assertTrue(all(e.boundary is not None for e in graph.edges if e.kind == 'gable_end'))
        from roof_generator.core.solve import problem, solve
        mesh = solve(graph, problem(graph, .5))
        self.assertIs(mesh.graph, graph)

    def test_candidate_rejects_forged_end_state(self):
        from dataclasses import replace
        candidate = prepare_generation(((0, 0), (12, 0), (12, 4), (4, 4), (4, 10), (0, 10))).selected
        state = candidate.ends.states[0]
        changed = replace(state, shape=EndShape.HIP)
        with self.assertRaises(UnsupportedRoofError):
            replace(candidate, ends=replace(candidate.ends, states=(changed,) + candidate.ends.states[1:]))


if __name__ == '__main__':
    unittest.main()
