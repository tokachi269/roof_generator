# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from dataclasses import replace
from python.graph_first.footprint import analyze
from python.graph_first.cells import decompose
from python.graph_first.parts import ArchitecturalPartGraph, Member, Part
from python.graph_first.graph import UnsupportedGraphError


class PartContractProof(unittest.TestCase):
    def rectangle(self):
        d = decompose(analyze(((0, 0), (12, 0), (12, 5), (0, 5))))
        c = d.cells[0]
        p = Part(
            0,
            (0,),
            (c.boundary,),
            tuple(s for side in c.sides for s in side.exterior),
            (),
            (0,),
        )
        pts = [d.vertices[v] for v in c.corners]
        bounds = (
            min(p[0] for p in pts),
            min(p[1] for p in pts),
            max(p[0] for p in pts),
            max(p[1] for p in pts),
        )
        axes = (int(bounds[3] - bounds[1] > bounds[2] - bounds[0]),)
        p = replace(p, axes=axes)
        m = Member(0, bounds, axes)
        return ArchitecturalPartGraph(d, (m,), (p,), (), (), ())

    def test_contract_is_not_roofgraph(self):
        g = self.rectangle()
        self.assertIsNone(g.inspect()["roof_topology"])
        self.assertEqual(g.parts[0].cells, (0,))
        self.assertFalse(hasattr(g, "faces"))

    def test_missing_membership_boundary_or_provenance_is_rejected(self):
        g = self.rectangle()
        for bad in (
            replace(g.parts[0], cells=()),
            replace(g.parts[0], boundaries=()),
            replace(g.parts[0], exterior=()),
            replace(g.parts[0], consumed=((0, 1),)),
        ):
            with self.assertRaises(UnsupportedGraphError):
                replace(g, parts=(bad,))


class CompoundInterpretationProof(unittest.TestCase):
    def test_compound_boundary_and_roles_from_literal_two_corner_members(self):
        from python.graph_first.partition_candidates import candidates
        from python.graph_first.part_interpretation import interpret
        from shapely.geometry import Polygon

        raw = ((0, 0), (18, 0), (18, 12), (14, 12), (14, 6), (4, 6), (4, 12), (0, 12))
        search = candidates(analyze(raw))
        graphs = [interpret(d) for d in search.candidates]
        self.assertEqual(len(graphs), 4)
        main_candidates = []
        for g in graphs:
            self.assertEqual(len(g.parts), 1)
            self.assertEqual(len(g.parts[0].cells), 3)
            self.assertEqual(len(g.parts[0].consumed), 2)
            pts = [
                g.decomposition.footprint.frame.world_xy(g.decomposition.vertices[v])
                for v in g.parts[0].boundaries[0]
            ]
            self.assertLess(Polygon(pts).symmetric_difference(Polygon(raw)).area, 1e-10)
            if all(
                len(r.options) == 1 and r.options[0].main is not None
                for r in g.relations
            ):
                mains = {r.options[0].main for r in g.relations}
                if len(mains) == 1:
                    main_candidates.append(g)
        self.assertEqual(len(main_candidates), 1)
        g = main_candidates[0]
        self.assertEqual({o.kind for r in g.relations for o in r.options}, {"corner"})
        self.assertEqual(
            [
                round(w * g.decomposition.footprint.frame.scale)
                for w in g.relations[0].options[0].widths
            ],
            [6, 4],
        )

    def test_literal_compound_corner_plus_middle_attachment(self):
        from python.graph_first.partition_candidates import candidates
        from python.graph_first.part_interpretation import interpret

        # A complete horizontal receiver, one end branch, one middle branch.
        raw = (
            (0, 0),
            (24, 0),
            (24, 6),
            (16, 6),
            (16, 14),
            (12, 14),
            (12, 6),
            (4, 6),
            (4, 12),
            (0, 12),
        )
        graphs = [interpret(d) for d in candidates(analyze(raw)).candidates]
        g = next(
            g
            for g in graphs
            if sorted(len(p.cells) for p in g.parts) == [1, 2]
            and {o.kind for r in g.relations for o in r.options}
            == {"corner", "side_attachment"}
        )
        self.assertEqual(len(g.adjacency), 1)
        self.assertEqual(sum(len(p.consumed) for p in g.parts), 1)
        self.assertEqual(sorted(c for p in g.parts for c in p.cells), [0, 1, 2])

    def test_adjacency_order_never_selects_a_different_group(self):
        from python.graph_first.partition_candidates import candidates
        from python.graph_first.part_interpretation import interpret

        fp = analyze(
            ((0, 0), (18, 0), (18, 12), (14, 12), (14, 6), (4, 6), (4, 12), (0, 12))
        )
        for d in candidates(fp).candidates:
            self.assertEqual(
                interpret(d).inspect(),
                interpret(replace(d, adjacency=tuple(reversed(d.adjacency)))).inspect(),
            )

    def test_all_cells_and_exterior_are_kept_on_unknown_grid_inputs(self):
        from python.tests.grid_footprints import generated
        from python.graph_first.partition_candidates import candidates
        from python.graph_first.part_interpretation import interpret
        from shapely.geometry import Polygon
        from shapely.ops import unary_union

        for raw in generated(count=30):
            search = candidates(analyze(raw), max_work=2048, max_candidates=256)
            for d in search.candidates:
                g = interpret(d)
                polygons = []
                for p in g.parts:
                    outlines = [
                        Polygon([d.vertices[v] for v in ring]) for ring in p.boundaries
                    ]
                    combined = unary_union(outlines)
                    expected = unary_union(
                        [
                            Polygon([d.vertices[v] for v in d.cells[c].corners])
                            for c in p.cells
                        ]
                    )
                    self.assertLess(combined.symmetric_difference(expected).area, 1e-12)
                    polygons.append(expected)
                self.assertLess(
                    unary_union(polygons)
                    .symmetric_difference(Polygon(d.footprint.vertices))
                    .area,
                    1e-12,
                )
                self.assertLess(
                    sum(p.area for p in polygons) - unary_union(polygons).area, 1e-12
                )
                for edge in range(len(d.footprint.vertices)):
                    spans = sorted(
                        s.interval
                        for p in g.parts
                        for s in p.exterior
                        if s.edge == edge
                    )
                    self.assertAlmostEqual(sum(b - a for a, b in spans), 1)
                    self.assertTrue(
                        all(abs(a[1] - b[0]) < 1e-9 for a, b in zip(spans, spans[1:]))
                    )

    def test_square_and_width_ambiguities_are_not_area_decisions(self):
        from python.graph_first.part_interpretation import interpret

        g = interpret(
            decompose(
                analyze(
                    (
                        (1, 0),
                        (2, 0),
                        (2, 1),
                        (3, 1),
                        (3, 2),
                        (2, 2),
                        (2, 3),
                        (1, 3),
                        (1, 2),
                        (0, 2),
                        (0, 1),
                        (1, 1),
                    )
                )
            )
        )
        self.assertEqual(sum(len(m.axes) == 2 for m in g.members), 2)
        self.assertTrue(all(len(r.options) == 2 for r in g.relations))
        self.assertIn("axis_ambiguity", {i.code for i in g.issues})
        self.assertTrue(all(o.main is None for r in g.relations for o in r.options))

    def test_mutating_a_member_geometry_or_relation_provenance_fails(self):
        from python.graph_first.part_interpretation import interpret

        g = interpret(
            decompose(analyze(((0, 0), (12, 0), (12, 4), (4, 4), (4, 10), (0, 10))))
        )
        bad = replace(g.members[0], bounds=(0, 0, 1, 1))
        with self.assertRaises(UnsupportedGraphError):
            replace(g, members=(bad,) + g.members[1:])
        bad = replace(g.relations[0], intervals=())
        with self.assertRaises(UnsupportedGraphError):
            replace(g, relations=(bad,))


if __name__ == "__main__":
    unittest.main()
