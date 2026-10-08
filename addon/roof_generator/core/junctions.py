# SPDX-License-Identifier: GPL-3.0-or-later
"""Published side-branch relations, recognized before any junction edits.

Laycock Fig. 6, Sugihara 2007 pp. 312–313 and Kada Section 2.4:
see docs/ROOF_COMPOSITION_RESEARCH.md for applicability and adaptation limits.
"""

from collections import defaultdict
from dataclasses import dataclass, asdict
import math

from .footprint import EPS, on_segment, sub
from .errors import UnsupportedRoofError, GenerationIssue


def port(graph, side):
    """A declared gable end; never discover ridge semantics from geometry."""
    return next(
        (
            i
            for i, v in enumerate(graph.vertices)
            if v.role == "ridge_end"
            and v.boundary is not None
            and v.boundary.edge == side
        ),
        None,
    )


@dataclass(frozen=True)
class AttachmentPort:
    host: int
    branch: int
    host_side: int
    branch_side: int
    shared: tuple[int, int]  # ordered in the host's CCW side direction
    branch_port: int  # index in the source primitive
    host_port: int | None  # consumed only by a terminal attachment
    kind: str
    host_width: float
    branch_width: float

    @property
    def equal_width(self):
        return abs(self.host_width - self.branch_width) <= 4 * EPS

    def inspect(self):
        return asdict(self)


def attachments(decomposition, primitives):
    """Local candidates from complete end / partial side and exterior ownership.

    A minimum subdivision may node one shared side into several atoms. Group
    those atoms by incident sides, requiring complete contiguous coverage.
    No footprint class, largest-cell score or mesh/plane calculation is used.
    """
    groups = defaultdict(list)
    for adjacent in decomposition.adjacency:
        key = tuple(sorted(zip(adjacent.cells, adjacent.sides)))
        groups[key].append(adjacent.interval)
    nodes = decomposition.vertices
    candidates = []
    for sides, atoms in sorted(groups.items()):
        for (host, hs), (branch, bs) in (sides, sides[::-1]):
            hc, bc = decomposition.cells[host], decomposition.cells[branch]
            hside, bside = hc.sides[hs], bc.sides[bs]
            branch_port = port(primitives[branch], bs)
            if branch_port is None or any(
                side.artificial for i, side in enumerate(bc.sides) if i != bs
            ):
                continue  # This operation consumes a leaf's complete end.
            if not any(
                e.vertices == tuple(sorted((hs, (hs + 1) % 4))) and e.kind == "eave"
                for e in primitives[host].edges
            ):
                continue
            a, b = (nodes[i] for i in hside.vertices)
            axis = sub(b, a)
            size = math.hypot(*axis)
            parameter = (
                lambda i: sum(x * y for x, y in zip(sub(nodes[i], a), axis)) / size
            )
            intervals = sorted(tuple(sorted(map(parameter, atom))) for atom in atoms)
            end = tuple(sorted(map(parameter, bside.vertices)))
            if (
                abs(intervals[0][0] - end[0]) > EPS
                or abs(intervals[-1][1] - end[1]) > EPS
                or any(abs(x[1] - y[0]) > EPS for x, y in zip(intervals, intervals[1:]))
                or end[0] < -EPS
                or end[1] > size + EPS
                or end[1] - end[0] >= size - EPS
            ):
                continue
            shared = tuple(sorted(bside.vertices, key=parameter))
            touching = set(shared).intersection(hside.vertices)
            host_port = None
            if len(touching) == 1:
                cut = next(iter(touching))
                reflex = next(i for i in shared if i != cut)
                near = (hs - 1) % 4 if cut == hside.vertices[0] else (hs + 1) % 4
                host_port = port(primitives[host], near)
                if host_port is None or reflex not in decomposition.footprint.reflex:
                    continue
                outer = next(i for i in hc.sides[near].vertices if i != cut)
                bi = bc.corners.index(cut)
                other = next(
                    i
                    for i in (bc.corners[(bi - 1) % 4], bc.corners[(bi + 1) % 4])
                    if i not in shared
                )
                if not on_segment(nodes[cut], nodes[outer], nodes[other]):
                    continue
                kind = "terminal"
            elif not touching and all(
                i in decomposition.footprint.reflex for i in shared
            ):
                kind = "middle"
            else:
                continue
            # Rectangle gable caps imply perpendicular ridge axes here. Width
            # is transverse to each ridge, not area or the long-axis heuristic.
            width_side = hc.sides[(hs + 1) % 4]
            candidates.append(
                AttachmentPort(
                    host,
                    branch,
                    hs,
                    bs,
                    shared,
                    branch_port,
                    host_port,
                    kind,
                    math.dist(*(nodes[i] for i in width_side.vertices)),
                    math.dist(*(nodes[i] for i in bside.vertices)),
                )
            )
    return tuple(candidates)


def plan(decomposition, primitives):
    """Recognize the whole arrangement; never apply a sequence of pairwise merges."""
    relations = attachments(decomposition, primitives)
    if len(decomposition.cells) == 2 and len(relations) == 1:
        relation = relations[0]
        if relation.kind == "terminal":
            return relations
    if not relations or any(r.kind != "middle" for r in relations):
        raise UnsupportedRoofError(
            "no complete supported middle-attachment arrangement; terminal graft requires one attachment",
            issues=(GenerationIssue("junction", "terminal_arrangement"),),
        )
    hosts = {r.host for r in relations}
    branches = {r.branch for r in relations}
    if (
        len(hosts) != 1
        or len(branches) != len(relations)
        or hosts.intersection(branches)
        or hosts.union(branches) != {c.id for c in decomposition.cells}
    ):
        raise UnsupportedRoofError(
            "attachment roles do not identify one host and exterior leaf branches; architectural aggregation is unresolved",
            issues=(GenerationIssue("junction", "host_arrangement"),),
        )
    if any(r.branch_width > r.host_width + 4 * EPS for r in relations):
        raise UnsupportedRoofError(
            "middle attachment requires a narrower or equal-width branch",
            issues=(GenerationIssue("junction", "branch_width"),),
        )
    # Published extension is locally reusable for disjoint narrow slots only.
    # Require separation even on opposite eaves; interacting extensions and
    # combined corner templates are deliberately outside this proof.
    host = decomposition.cells[next(iter(hosts))]
    origin = decomposition.vertices[host.corners[0]]
    first = relations[0]
    a, b = (decomposition.vertices[i] for i in host.sides[first.host_side].vertices)
    axis = sub(b, a)
    size = math.hypot(*axis)
    coordinate = (
        lambda i: sum(
            x * y for x, y in zip(sub(decomposition.vertices[i], origin), axis)
        )
        / size
    )
    slots = sorted(tuple(sorted(map(coordinate, r.shared))) for r in relations)
    if len(relations) > 1 and any(r.equal_width for r in relations):
        # Kada's compatible cross block: two opposite complete equal-width
        # openings have the same longitudinal interval. They share ONE ridge
        # junction, rather than two coincident independent T replacements.
        if (
            len(relations) == 2
            and all(r.equal_width for r in relations)
            and (relations[0].host_side - relations[1].host_side) % 4 == 2
            and all(abs(a - b) <= 4 * EPS for a, b in zip(slots[0], slots[1]))
        ):
            return relations
        raise UnsupportedRoofError(
            "multiple equal-width attachments lack compatible opposite shared ports",
            issues=(GenerationIssue("junction", "equal_width_ports"),),
        )
    if any(a[1] + EPS >= b[0] for a, b in zip(slots, slots[1:])):
        raise UnsupportedRoofError(
            "branch attachment slots interact; no independent junction composition is proved",
            issues=(GenerationIssue("junction", "interacting_slots"),),
        )
    return relations
