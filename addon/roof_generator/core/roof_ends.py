# SPDX-License-Identifier: GPL-3.0-or-later
"""Global roof-end combinations, before local incidence templates.

Hu 3.4/3.5: one-line and T forbid triangular roof sides; an L-junction has
shared and T options, constrained simultaneously by other incident ends.
`shared` denotes ownership by a compound junction, not a third rectangle roof
primitive. The gable request selects gabled free exterior ends; R=0 alone does
not mean that a geometric junction/merge has been implemented.
"""

from dataclasses import dataclass, asdict
from enum import Enum
from itertools import product
from .footprint import EPS
from .errors import UnsupportedRoofError, GenerationIssue


class EndShape(str, Enum):
    GABLE = "gable"
    HIP = "hip"
    SHARED = "shared"


@dataclass(frozen=True, order=True)
class End:
    member: int
    side: int


@dataclass(frozen=True)
class EndChoice:
    cells: tuple[int, int]
    kind: str
    states: tuple[tuple[End, EndShape], ...]


@dataclass(frozen=True)
class EndRule:
    cells: tuple[int, int]
    choices: tuple[EndChoice, ...]


@dataclass(frozen=True)
class EndState:
    end: End
    shape: EndShape
    connection: str


@dataclass(frozen=True)
class RoofEnds:
    states: tuple[EndState, ...]
    joints: tuple[EndChoice, ...]

    def inspect(self):
        return asdict(self)


def configurations(ends, rules, equalities=()):
    """Intersect all end obligations; then require symmetric resolved choices.

    There is no operation-availability input and no sequential pairwise repair.
    Shared ownership cannot overwrite an end forced gabled by another rule.
    """
    ends = tuple(sorted(ends))
    for joints in product(*(r.choices for r in rules)):
        assigned = {}
        ownership = {}
        conflict = False
        for joint in joints:
            for end, shape in joint.states:
                if end in assigned and assigned[end] != shape:
                    conflict = True
                    break
                if shape == EndShape.SHARED and end in ownership and ownership[end] != joint.cells:
                    conflict = True
                    break
                assigned[end] = shape
                if shape == EndShape.SHARED:
                    ownership[end] = joint.cells
            if conflict:
                break
        if conflict:
            continue
        shapes = {end: assigned.get(end, EndShape.GABLE) for end in ends}
        if any(shapes[a] != shapes[b] for a, b in equalities):
            continue
        states = []
        for end in ends:
            kinds = {j.kind for j in joints if any(e == end for e, _ in j.states)}
            # A continuation may coexist with an extension onto its receiving
            # member; the latter does not consume that member's short end.
            connection = "shared" if "shared" in kinds else "continuation" if "continuation" in kinds else "extension" if "extension" in kinds else "exterior"
            states.append(EndState(end, shapes[end], connection))
        yield RoofEnds(tuple(states), tuple(sorted(joints, key=lambda j: j.cells)))


def end_rules(resolved):
    d = resolved.decomposition
    ends = []
    for m, axis in zip(resolved.architecture.members, resolved.axes):
        c = d.cells[m.cell]
        for index, side in enumerate(c.sides):
            a, b = (d.vertices[i] for i in side.vertices)
            if abs(a[axis] - b[axis]) <= EPS:
                ends.append(End(m.cell, index))
    rules = []
    unresolved = []
    for relation in resolved.relations:
        option = relation.options[0]
        if option.kind == "continuation":
            states = tuple((End(c, s), EndShape.GABLE) for c, s in zip(relation.cells, relation.sides))
            choices = (EndChoice(relation.cells, "continuation", states),)
        elif option.kind in {"corner", "side_attachment"}:
            branch = End(option.branch, relation.sides[relation.cells.index(option.branch)])
            extension = EndChoice(relation.cells, "extension", ((branch, EndShape.GABLE),))
            if option.kind == "side_attachment":
                choices = (extension,)
            else:
                host = option.receiver
                hs = relation.sides[relation.cells.index(host)]
                hc = d.cells[host]
                shared = {v for atom in relation.intervals for v in atom}
                touching = shared.intersection(hc.sides[hs].vertices)
                if len(touching) != 1:
                    raise UnsupportedRoofError("corner end has no unique incident receiver end")
                cut = next(iter(touching))
                near = (hs - 1) % 4 if cut == hc.sides[hs].vertices[0] else (hs + 1) % 4
                receiver = End(host, near)
                choices = (EndChoice(relation.cells, "shared", ((receiver, EndShape.SHARED), (branch, EndShape.SHARED))), extension)
        else:
            unresolved.append(GenerationIssue("relation", ("internal_" if resolved.internal(relation) else "inter_part_") + option.kind, relation.cells))
            continue
        rules.append(EndRule(relation.cells, choices))
    if unresolved:
        raise UnsupportedRoofError("no resolved roof-end combination for " + unresolved[0].code, issues=tuple(unresolved))
    return tuple(ends), tuple(rules)


def symmetric_ends(resolved, ends, clusters):
    """Exact whole-member reflected ends; split-root matches are not guessed."""
    d = resolved.decomposition
    members = resolved.architecture.members
    pairs = set()
    for cluster in clusters:
        axis, mid = cluster.axis, cluster.coordinate
        for a, b in cluster.pairs:
            box = list(members[a].bounds)
            box[axis], box[axis + 2] = 2 * mid - box[axis + 2], 2 * mid - box[axis]
            if max(abs(x - y) for x, y in zip(box, members[b].bounds)) > 4 * EPS:
                continue
            for first in (e for e in ends if e.member == a):
                points = tuple(d.vertices[v] for v in d.cells[a].sides[first.side].vertices)
                mirror = tuple(tuple(2 * mid - p[k] if k == axis else p[k] for k in (0, 1)) for p in points)
                for second in (e for e in ends if e.member == b):
                    targets = tuple(d.vertices[v] for v in d.cells[b].sides[second.side].vertices)
                    if all(any(max(abs(x - y) for x, y in zip(p, q)) <= 4 * EPS for q in targets) for p in mirror):
                        pairs.add(tuple(sorted((first, second))))
    return tuple(sorted(pairs))


def roof_configurations(resolved, clusters=()):
    ends, rules = end_rules(resolved)
    yield from configurations(ends, rules, symmetric_ends(resolved, ends, clusters))
