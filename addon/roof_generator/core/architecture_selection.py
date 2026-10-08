# SPDX-License-Identifier: GPL-3.0-or-later
"""Hu 3.3 terms, exact reflection components and honest uncertain recommendations."""

from dataclasses import dataclass, asdict
from .footprint import EPS
from .architecture import analyze_parts, build_parts
from .partition_candidates import CandidateSearch
from .architecture_models import ArchitecturalPartGraph


@dataclass(frozen=True)
class Policy:
    fragment_metres: float = 3.0  # Hu 5.2; not a numerical tolerance
    metres_per_unit: float = 1.0

    def __post_init__(self):
        import math

        if not all(
            math.isfinite(x) and x > 0
            for x in (self.fragment_metres, self.metres_per_unit)
        ):
            raise ValueError(
                "fragment threshold and unit conversion must be finite and positive"
            )


@dataclass(frozen=True)
class SymmetryCluster:
    axis: int  # coordinate normal to the reflection axis
    coordinate: float
    pairs: tuple[tuple[int, int], ...]  # source cells, including split root pairs


def _touch(a, b):
    return any(
        abs(a[2 + k] - b[k]) <= 4 * EPS or abs(b[2 + k] - a[k]) <= 4 * EPS
        for k in (0, 1)
    ) and any(min(a[2 + k], b[2 + k]) - max(a[k], b[k]) > 4 * EPS for k in (0, 1))


def symmetry_clusters(analysis):
    """Maximal exact reflected connected regions, seeded by split member axes.

    This uses Hu's four connected reflection conditions, with 2D member regions
    instead of extended analytic segments. It is a conservative, documented
    adaptation; arbitrary connected subgraphs or near-symmetries are not scored.
    """
    roots = {}
    for m in analysis.members:
        for axis in m.axes:
            mid = (m.bounds[axis] + m.bounds[2 + axis]) / 2
            roots.setdefault((axis, round(mid, 10)), mid)
    result = []
    for key in sorted(roots):
        axis, mid = key[0], roots[key]
        halves = [[], []]
        for m in analysis.members:
            for side in (0, 1):
                box = list(m.bounds)
                if side:
                    box[axis] = max(box[axis], mid)
                else:
                    box[2 + axis] = min(box[2 + axis], mid)
                if box[2 + axis] - box[axis] > 4 * EPS:
                    halves[side].append((m.cell, tuple(box)))
        positive = halves[1]
        matched = {}
        for i, (cell, b) in enumerate(halves[0]):
            mirror = list(b)
            mirror[axis] = 2 * mid - b[2 + axis]
            mirror[2 + axis] = 2 * mid - b[axis]
            j = next(
                (
                    j
                    for j, (_, q) in enumerate(positive)
                    if max(abs(a - b) for a, b in zip(mirror, q)) <= 4 * EPS
                ),
                None,
            )
            if j is not None:
                matched[i] = j
        remaining = set(matched)
        while remaining:
            todo = [min(remaining)]
            component = set()
            while todo:
                i = todo.pop()
                if i in component:
                    continue
                component.add(i)
                todo.extend(
                    j
                    for j in remaining - component
                    if _touch(halves[0][i][1], halves[0][j][1])
                    and _touch(positive[matched[i]][1], positive[matched[j]][1])
                )
            remaining -= component
            # A paired root straddles this axis; the two sides must be connected.
            crosses = any(
                halves[0][i][0] == positive[matched[i]][0]
                and abs(halves[0][i][1][2 + axis] - mid) <= 4 * EPS
                and abs(positive[matched[i]][1][axis] - mid) <= 4 * EPS
                for i in component
            )
            if len(component) >= 2 and crosses:
                pairs = tuple(
                    sorted(
                        (halves[0][i][0], positive[matched[i]][0]) for i in component
                    )
                )
                result.append(SymmetryCluster(axis, mid, pairs))
    return tuple(result)


@dataclass(frozen=True)
class Evaluation:
    fragments: tuple[int, ...]
    parallel_fixed: tuple[tuple[int, int], ...]
    parallel_possible: tuple[tuple[int, int], ...]
    symmetry: tuple[SymmetryCluster, ...]
    score: tuple[int, int]  # safe lower/upper bound while square axes are unresolved


def evaluate(d, analysis, policy=Policy()):
    metric = d.footprint.frame.scale * policy.metres_per_unit
    fragments = tuple(
        m.cell
        for m in analysis.members
        if min(m.bounds[2] - m.bounds[0], m.bounds[3] - m.bounds[1]) * metric
        < policy.fragment_metres - EPS * metric
    )
    fixed = []
    possible = []
    for r in analysis.relations:
        parallel = [o.kind == "parallel" for o in r.options]
        if all(parallel):
            fixed.append(r.cells)
        if any(parallel):
            possible.append(r.cells)
    symmetry = symmetry_clusters(analysis)
    origin = -len(fragments) + len(symmetry)
    return Evaluation(
        fragments,
        tuple(fixed),
        tuple(possible),
        symmetry,
        (origin - 2 * len(possible), origin - 2 * len(fixed)),
    )


def retained_indices(search, evaluations):
    if not search.complete:
        return ()
    if len(evaluations) != len(search.candidates):
        raise ValueError("evaluation must cover every candidate")
    best_lower = max(e.score[0] for e in evaluations)
    return tuple(i for i, e in enumerate(evaluations) if e.score[1] >= best_lower)


@dataclass(frozen=True)
class Recommendation:
    search: CandidateSearch
    policy: Policy
    evaluations: tuple[Evaluation, ...]
    retained: tuple[tuple[int, ArchitecturalPartGraph], ...]

    @property
    def status(self):
        if not self.search.complete:
            return "incomplete"
        if len(self.retained) > 1 or any(
            self.evaluations[i].score[0] != self.evaluations[i].score[1]
            for i, _ in self.retained
        ):
            return "ambiguous"
        issues = self.retained[0][1].issues
        if any(i.code == "axis_ambiguity" for i in issues):
            return "ambiguous"
        return "partial" if issues else "interpreted"

    def inspect(self):
        return {
            "status": self.status,
            "search": self.search.inspect(),
            "policy": asdict(self.policy),
            "evaluations": [asdict(e) for e in self.evaluations],
            "retained": [
                {"candidate": i, "graph": g.inspect()} for i, g in self.retained
            ],
            "semantically_unique": self.status == "interpreted",
            "uniqueness_scope": "part relation model within the evaluated candidate family; no unique real roof is claimed",
            "roof_topology": None,
        }


def recommend(search, policy=Policy()):
    analyses = tuple(analyze_parts(d) for d in search.candidates)
    evaluations = tuple(
        evaluate(d, a, policy) for d, a in zip(search.candidates, analyses)
    )
    retained = tuple(
        (i, build_parts(search.candidates[i], analyses[i]))
        for i in retained_indices(search, evaluations)
    )
    return Recommendation(search, policy, evaluations, retained)
