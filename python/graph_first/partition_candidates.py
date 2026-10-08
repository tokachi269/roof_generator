# SPDX-License-Identifier: GPL-3.0-or-later
"""Hu et al. 3.1 minimum candidate family, with explicit resource boundaries."""

from dataclasses import dataclass, replace
from itertools import product
from .footprint import EPS
from .rectangle_partition import (
    good_diagonals,
    select_diagonals,
    complete_cuts,
    subdivide,
    Cut,
)
from .cells import from_subdivision
from .errors import UnsupportedRoofError


@dataclass(frozen=True)
class Symmetry:
    matrix: tuple[tuple[int, int], tuple[int, int]]
    center: tuple[float, float]
    vertices: tuple[int, ...]

    def apply(self, p):
        q = tuple(p[k] - self.center[k] for k in (0, 1))
        return tuple(
            self.center[k] + sum(a * b for a, b in zip(row, q))
            for k, row in enumerate(self.matrix)
        )


def symmetries(fp):
    """Exact dihedral isometries of this orthogonal boundary; no rectification."""
    pts = fp.vertices
    center = tuple(
        (min(p[k] for p in pts) + max(p[k] for p in pts)) / 2 for k in (0, 1)
    )
    result = []
    for swap, sx, sy in product((False, True), (-1, 1), (-1, 1)):
        matrix = ((0, sx), (sy, 0)) if swap else ((sx, 0), (0, sy))
        candidate = Symmetry(matrix, center, ())
        image = tuple(candidate.apply(p) for p in pts)
        mapping = tuple(
            next(
                (
                    i
                    for i, q in enumerate(pts)
                    if max(abs(a - b) for a, b in zip(p, q)) <= 4 * EPS
                ),
                -1,
            )
            for p in image
        )
        if -1 not in mapping and len(set(mapping)) == len(pts):
            # A vertex permutation must also preserve actual boundary incidence.
            if all(
                (mapping[(i + 1) % len(pts)] - mapping[i]) % len(pts)
                in (1, len(pts) - 1)
                for i in range(len(pts))
            ):
                result.append(replace(candidate, vertices=mapping))
    return tuple(result)


def maximum_sets(selection, visit=None):
    """Exactly one endpoint per matched edge; all unmatched vertices are forced.

    |I| = |V| - |M| forces this property for every maximum independent set.
    Reject conflicts at each branch. Enumeration operates only on indices.
    """
    matched = {v for pair in selection.matching for v in pair}
    forced = frozenset(set(range(len(selection.diagonals))) - matched)
    neighbors = {v: set() for v in range(len(selection.diagonals))}
    for a, b in selection.conflicts:
        neighbors[a].add(b)
        neighbors[b].add(a)
    stack = [(0, forced)]
    while stack:
        if visit:
            visit()
        k, chosen = stack.pop()
        if k == len(selection.matching):
            yield tuple(sorted(chosen))
            continue
        for v in reversed(selection.matching[k]):
            if not neighbors[v].intersection(chosen):
                stack.append((k + 1, chosen.union((v,))))


def signature(d):
    """Coordinate-only identity, independent of noding/certificate choices."""
    return tuple(
        sorted(
            tuple(sorted(tuple(round(x, 10) for x in d.vertices[i]) for i in c.corners))
            for c in d.cells
        )
    )


@dataclass(frozen=True)
class CandidateSearch:
    candidates: tuple
    maximum_sets: int
    work: int
    complete: bool
    reason: str | None
    symmetries: tuple[Symmetry, ...]
    family: str = "both axes in canonical reflex order, plus footprint symmetry images"

    @property
    def symmetry_orbits(self):
        """Actual candidate equivalence under footprint isometries, not roof choice."""
        ids = {signature(d): i for i, d in enumerate(self.candidates)}
        neighbors = {i: set() for i in ids.values()}
        for i, d in enumerate(self.candidates):
            for symmetry in self.symmetries:
                image = tuple(
                    sorted(
                        tuple(
                            sorted(
                                tuple(
                                    round(x, 10) for x in symmetry.apply(d.vertices[v])
                                )
                                for v in c.corners
                            )
                        )
                        for c in d.cells
                    )
                )
                j = ids.get(image)
                if j is None:
                    if self.complete:
                        raise UnsupportedRoofError(
                            "completed candidate family is not symmetry closed"
                        )
                else:
                    neighbors[i].add(j)
                    neighbors[j].add(i)
        result = []
        remaining = set(neighbors)
        while remaining:
            todo = [min(remaining)]
            group = set()
            while todo:
                i = todo.pop()
                if i in group:
                    continue
                group.add(i)
                todo.extend(neighbors[i] - group)
            remaining -= group
            result.append(tuple(sorted(group)))
        return tuple(result)

    def inspect(self):
        return {
            "candidate_count": len(self.candidates),
            "maximum_sets": self.maximum_sets,
            "work": self.work,
            "complete": self.complete,
            "reason": self.reason,
            "family": self.family,
            "symmetry_orbits": self.symmetry_orbits,
            "symmetries": [
                {"matrix": s.matrix, "vertices": s.vertices} for s in self.symmetries
            ],
        }


def candidates(fp, *, max_candidates=4096, max_work=65536):
    """Enumerate certified minimum subdivisions, never roof geometry.

    No optimal recommendation may use a search with complete=False. Complete
    refers to the documented direction/order family, not arbitrary cut orders.
    """
    if max_candidates < 1 or max_work < 1:
        raise ValueError("candidate/work budgets must be positive")
    base = select_diagonals(fp, good_diagonals(fp))
    transforms = symmetries(fp)
    pool = {}
    work = sets = 0
    reason = None
    diagonal_ids = {tuple(sorted(d.endpoints)): i for i, d in enumerate(base.diagonals)}
    seen_cuts = set()

    class BudgetExhausted(Exception):
        pass

    def visit():
        nonlocal work, reason
        if work >= max_work:
            reason = "partition work budget exhausted; recommendation unavailable"
            raise BudgetExhausted
        work += 1

    def add(selection, cuts):
        nonlocal reason
        visit()
        cut_key = tuple(
            sorted(
                tuple(sorted(tuple(round(x, 10) for x in p) for p in pair))
                for pair in [
                    tuple(fp.vertices[v] for v in base.diagonals[i].endpoints)
                    for i in selection.selected
                ]
                + [(c.start, c.end) for c in cuts]
            )
        )
        if cut_key in seen_cuts:
            return True
        seen_cuts.add(cut_key)
        d = from_subdivision(fp, subdivide(fp, selection, cuts))
        key = signature(d)
        if key not in pool and len(pool) >= max_candidates:
            reason = "minimum candidate budget exhausted; recommendation unavailable"
            return False
        pool.setdefault(key, d)
        return True

    # Keep the established deterministic partition as the first generated witness.
    try:
        add(base, complete_cuts(fp, base))
        for chosen in maximum_sets(base, visit):
            sets += 1
            selection = replace(base, selected=chosen)
            covered = {v for i in chosen for v in base.diagonals[i].endpoints}
            for axes in product((0, 1), repeat=len(set(fp.reflex) - covered)):
                cuts = complete_cuts(fp, selection, axes)
                if not add(selection, cuts):
                    break
                for symmetry in transforms:
                    if symmetry.matrix == ((1, 0), (0, 1)):
                        continue
                    selected = tuple(
                        sorted(
                            diagonal_ids[
                                tuple(
                                    sorted(
                                        symmetry.vertices[v]
                                        for v in base.diagonals[i].endpoints
                                    )
                                )
                            ]
                            for i in chosen
                        )
                    )
                    transformed = tuple(
                        Cut(
                            symmetry.vertices[c.source],
                            symmetry.apply(c.start),
                            symmetry.apply(c.end),
                        )
                        for c in cuts
                    )
                    if not add(replace(base, selected=selected), transformed):
                        break
                if reason:
                    break
            if reason:
                break
    except BudgetExhausted:
        pass
    return CandidateSearch(
        tuple(pool[k] for k in sorted(pool)),
        sets,
        work,
        reason is None,
        reason,
        transforms,
    )
