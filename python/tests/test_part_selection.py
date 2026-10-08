# SPDX-License-Identifier: GPL-3.0-or-later
"""Published rule terms, exact reflection witnesses, ambiguous candidate proofs."""

import itertools
import json
import math
from pathlib import Path
from dataclasses import replace
import subprocess
import sys
import unittest
from python.graph_first.footprint import analyze
from python.graph_first.partition_candidates import candidates, signature
from python.graph_first.part_interpretation import analyze_parts
from python.graph_first.part_selection import recommend, Policy

ROOT = Path(__file__).resolve().parents[2]


def inputs():
    rows = json.loads(
        (ROOT / "python/tests/fixtures/rectangle_partition.json").read_text()
    )
    result = {
        r["name"]: r["footprint"]
        for r in rows
        if r["name"] in ("orthogonal_U", "cross", "residential_multi_reflex")
    }
    for name in ("grid_14", "grid_20", "grid_40"):
        result[name] = json.loads(
            (ROOT / f"python/docs/partition/{name}.json").read_text()
        )["input"]["footprint"]
    return result


def semantics(rec):
    rows = []
    for i, g in rec.retained:
        groups = tuple(
            sorted(
                tuple(
                    sorted(
                        tuple(round(v, 8) for v in g.members[c].bounds) for c in p.cells
                    )
                )
                for p in g.parts
            )
        )
        rows.append(
            (
                signature(g.decomposition),
                groups,
                rec.evaluations[i].score,
                tuple(sorted(x.code for x in g.issues)),
            )
        )
    return sorted(rows)


class SelectionProof(unittest.TestCase):
    def test_u_retains_two_symmetric_compound_interpretations(self):
        out = recommend(candidates(analyze(inputs()["orthogonal_U"])))
        self.assertEqual(len(out.search.candidates), 4)
        self.assertEqual(len(out.retained), 2)
        self.assertEqual(out.status, "ambiguous")
        self.assertFalse(out.inspect()["semantically_unique"])
        for i, g in out.retained:
            self.assertEqual(out.evaluations[i].score, (1, 1))
            self.assertEqual([p.cells for p in g.parts], [(0, 1, 2)])
            self.assertEqual(len(g.relations), 2)
            self.assertEqual(len(g.parts[0].consumed), 2)
            self.assertEqual(
                {o.kind for r in g.relations for o in r.options}, {"corner"}
            )
        self.assertNotEqual(
            [o.receiver for r in out.retained[0][1].relations for o in r.options],
            [o.receiver for r in out.retained[1][1].relations for o in r.options],
        )

    def test_cross_keeps_two_main_directions_and_square_options(self):
        out = recommend(candidates(analyze(inputs()["cross"])))
        self.assertEqual(len(out.search.candidates), 2)
        self.assertEqual(len(out.retained), 2)
        self.assertEqual(out.status, "ambiguous")
        main_axes = []
        self.assertEqual(out.search.symmetry_orbits, ((0, 1),))
        for _, g in out.retained:
            non_square = [m for m in g.members if len(m.axes) == 1]
            self.assertEqual(len(non_square), 1)
            main_axes.append(non_square[0].axes[0])
            self.assertTrue(
                all(
                    any(o.kind == "side_attachment" for o in r.options)
                    for r in g.relations
                )
            )
        self.assertEqual(set(main_axes), {0, 1})
        self.assertEqual(out.evaluations[0].score, out.evaluations[1].score)

    def test_residential_groups_three_members_without_losing_the_middle_branch(self):
        out = recommend(candidates(analyze(inputs()["residential_multi_reflex"])))
        self.assertEqual(len(out.retained), 1)
        i, g = out.retained[0]
        self.assertEqual(out.evaluations[i].score, (0, 0))
        self.assertEqual(sorted(len(p.cells) for p in g.parts), [1, 3])
        self.assertEqual(sum(len(p.consumed) for p in g.parts), 2)
        self.assertEqual(len(g.adjacency), 1)
        self.assertEqual(
            sum(o.kind == "side_attachment" for r in g.relations for o in r.options), 1
        )
        self.assertEqual(out.status, "partial")
        self.assertIn("width_roles", {x.code for x in g.issues})

    def test_parallel_score_bounds_cover_all_axis_assignments(self):
        raw = inputs()["cross"]
        out = recommend(candidates(analyze(raw)))
        for d, e in zip(out.search.candidates, out.evaluations):
            # Explicit square axes, independent classification using shared coordinate.
            boxes = []
            domains = []
            for cell in d.cells:
                pts = [d.vertices[v] for v in cell.corners]
                sizes = [
                    max(p[k] for p in pts) - min(p[k] for p in pts) for k in (0, 1)
                ]
                boxes.append(sizes)
                domains.append(
                    (0, 1)
                    if abs(sizes[0] - sizes[1]) < 1e-8
                    else (int(sizes[1] > sizes[0]),)
                )
            for axes in itertools.product(*domains):
                parallel = set()
                for a in d.adjacency:
                    p, q = (d.vertices[v] for v in a.interval)
                    side_axis = int(abs(p[1] - q[1]) > 1e-8)
                    if all(axes[c] == side_axis for c in a.cells):
                        parallel.add(a.cells)
                literal = -3 - 2 * len(parallel) + len(e.symmetry)
                self.assertLessEqual(e.score[0], literal)
                self.assertGreaterEqual(e.score[1], literal)

    def test_symmetry_cluster_has_independent_reflected_region_witness(self):
        from shapely.geometry import box
        from shapely import affinity

        for raw in inputs().values():
            out = recommend(candidates(analyze(raw)))
            for d, e in zip(out.search.candidates, out.evaluations):
                for cluster in e.symmetry:
                    self.assertGreaterEqual(len(cluster.pairs), 2)
                    for a, b in cluster.pairs:
                        ps = [
                            [d.vertices[v] for v in d.cells[c].corners] for c in (a, b)
                        ]
                        bounds = [
                            (
                                min(p[0] for p in v),
                                min(p[1] for p in v),
                                max(p[0] for p in v),
                                max(p[1] for p in v),
                            )
                            for v in ps
                        ]
                        clip = list(bounds[0])
                        clip[2 + cluster.axis] = min(
                            clip[2 + cluster.axis], cluster.coordinate
                        )
                        source = box(*clip)
                        target = list(bounds[1])
                        target[cluster.axis] = max(
                            target[cluster.axis], cluster.coordinate
                        )
                        mirror = affinity.scale(
                            source,
                            xfact=-1 if cluster.axis == 0 else 1,
                            yfact=-1 if cluster.axis == 1 else 1,
                            origin=(
                                cluster.coordinate if cluster.axis == 0 else 0,
                                cluster.coordinate if cluster.axis == 1 else 0,
                            ),
                        )
                        self.assertLess(
                            mirror.symmetric_difference(box(*target)).area, 1e-12
                        )

    def test_fragment_unit_policy_never_discards_members(self):
        raw = ((0, 0), (12, 0), (12, 2), (2, 2), (2, 8), (0, 8))
        a = recommend(candidates(analyze(raw)))
        b = recommend(
            candidates(analyze(tuple((x * 100, y * 100) for x, y in raw))),
            Policy(metres_per_unit=0.01),
        )
        self.assertEqual(
            [e.score for e in a.evaluations], [e.score for e in b.evaluations]
        )
        self.assertTrue(all(len(e.fragments) == 2 for e in a.evaluations))
        self.assertTrue(
            all(
                sorted(c for p in g.parts for c in p.cells) == [0, 1]
                for _, g in a.retained
            )
        )

    def test_budget_failure_has_no_retained_recommendation(self):
        out = recommend(candidates(analyze(inputs()["orthogonal_U"]), max_work=1))
        self.assertEqual(out.status, "incomplete")
        self.assertEqual(out.retained, ())
        self.assertFalse(out.inspect()["semantically_unique"])

    def test_whole_recommendation_invariant_under_input_and_adjacency_permutations(
        self,
    ):
        a = 0.371
        c, s = math.cos(a), math.sin(a)
        for raw in inputs().values():
            points = tuple(map(tuple, raw))
            base = recommend(candidates(analyze(points)))
            expected = semantics(base)
            variants = (
                points[3:] + points[:3],
                tuple(reversed(points)),
                tuple((13 + c * x - s * y, -7 + s * x + c * y) for x, y in points),
                points[:1]
                + (tuple((x + y) / 2 for x, y in zip(points[0], points[1])),)
                + points[1:],
            )
            for variant in variants:
                actual = recommend(candidates(analyze(variant)))
                self.assertEqual(semantics(actual), expected)
            search = replace(
                base.search,
                candidates=tuple(
                    replace(d, adjacency=tuple(reversed(d.adjacency)))
                    for d in base.search.candidates
                ),
            )
            self.assertEqual(semantics(recommend(search)), expected)

    def test_runtime_does_not_import_roofs_solver_or_polygon_libraries(self):
        script = """
import importlib.abc,sys
sys.path.insert(0,sys.argv[1])
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,name,path=None,target=None):
  if name.split('.')[0] in {'shapely','numpy','roof_generator'} or name.endswith(('.topology','.geometry','.connections')):
   raise ImportError('forbidden dependency '+name)
sys.meta_path.insert(0,Block())
from python.graph_first.footprint import analyze
from python.graph_first.partition_candidates import candidates
from python.graph_first.part_selection import recommend
out=recommend(candidates(analyze(((0,0),(18,0),(18,12),(14,12),(14,6),(4,6),(4,12),(0,12)))))
assert out.retained
assert out.inspect()['roof_topology'] is None
"""
        subprocess.run(
            [sys.executable, "-I", "-c", script, str(ROOT)],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
