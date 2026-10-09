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


def attachments(resolved, primitives):
    """Bind architecture-declared roles/kinds to complete local topology ports.

    A minimum subdivision may node one shared side into several atoms. Group
    those atoms by incident sides, requiring complete contiguous coverage.
    Checks prove applicability; they never rediscover receiver/branch or kind.
    """
    decomposition = resolved.layout
    blockers = tuple(
        GenerationIssue("relation", ("internal_" if resolved.internal(r) else "inter_part_") + r.options[0].kind, r.cells)
        for r in resolved.relations if r.options[0].kind not in {"corner", "side_attachment"}
    )
    if blockers:
        raise UnsupportedRoofError("no implemented architecture template for " + blockers[0].code, issues=blockers)
    if resolved.ends is None:
        raise UnsupportedRoofError("junction plan requires resolved roof end configuration")
    decisions = {j.cells: j for j in resolved.ends.joints}
    nodes = decomposition.vertices
    candidates = []
    for relation in resolved.relations:
        option = relation.options[0]
        decision = decisions[relation.cells]
        if (option.kind == "corner" and decision.kind == "extension"
            and (len(resolved.relations) != 1 or option.widths[1] > option.widths[0] + 4 * EPS)):
            raise UnsupportedRoofError(
                "L/T extension requires one isolated narrower or equal-width branch",
                issues=(GenerationIssue("junction", "corner_extension", relation.cells),),
            )
        atoms = relation.intervals
        host, branch = option.receiver, option.branch
        hs = relation.sides[relation.cells.index(host)]
        bs = relation.sides[relation.cells.index(branch)]
        hc, bc = decomposition.supports[host], decomposition.supports[branch]
        hside, bside = hc.sides[hs], bc.sides[bs]
        branch_port = port(primitives[branch], bs)
        if branch_port is None or any(
            side.interior for i, side in enumerate(bc.sides) if i != bs
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
        if decision.kind == "shared" and len(touching) == 1:
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
        elif decision.kind == "extension" and (
            (not touching and all(i in decomposition.footprint.reflex for i in shared))
            or (option.kind == "corner" and len(touching) == 1
                and all(i in decomposition.footprint.reflex for i in set(shared) - touching))
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
                *option.widths,
            )
        )
    if len(candidates) != len(resolved.relations):
        raise UnsupportedRoofError(
            "declared architecture lacks a complete applicable port arrangement",
            issues=(GenerationIssue("junction", "attachment_applicability"),),
        )
    return tuple(candidates)


def plan(resolved, primitives):
    """Recognize the whole arrangement; never apply a sequence of pairwise merges."""
    decomposition = resolved.layout
    relations = attachments(resolved, primitives)
    if len(decomposition.supports) == 2 and len(relations) == 1:
        relation = relations[0]
        if relation.kind == "terminal":
            return relations
    if relations and all(r.kind == "terminal" for r in relations):
        hosts = {r.host for r in relations}
        branches = {r.branch for r in relations}
        if (
            len(hosts) == 1
            and len(branches) == len(relations)
            and not hosts.intersection(branches)
            and hosts.union(branches) == {c.id for c in decomposition.supports}
            and len({r.host_port for r in relations}) == len(relations)
        ):
            return relations
        raise UnsupportedRoofError(
            "terminal attachments need distinct receiver ends and exterior leaf branches",
            issues=(GenerationIssue("junction", "terminal_arrangement"),),
        )
    if {r.kind for r in relations} == {"terminal", "middle"}:
        return _mixed_plan(decomposition, primitives, relations)
    if not relations or any(r.kind != "middle" for r in relations):
        raise UnsupportedRoofError(
            "no complete supported terminal/middle attachment arrangement",
            issues=(GenerationIssue("junction", "terminal_arrangement"),),
        )
    hosts = {r.host for r in relations}
    branches = {r.branch for r in relations}
    if (
        len(hosts) != 1
        or len(branches) != len(relations)
        or hosts.intersection(branches)
        or hosts.union(branches) != {c.id for c in decomposition.supports}
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
    host = decomposition.supports[next(iter(hosts))]
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


def _mixed_plan(d, primitives, relations):
    """Existing port rewrites with disjoint receiver-end and side neighborhoods."""
    terminals = tuple(r for r in relations if r.kind == "terminal")
    middles = tuple(r for r in relations if r.kind == "middle")
    hosts = {r.host for r in relations}
    branches = {r.branch for r in relations}
    if (
        len(hosts) != 1
        or len(branches) != len(relations)
        or hosts & branches
        or hosts | branches != {c.id for c in d.supports}
        or len({r.host_port for r in terminals}) != len(terminals)
    ):
        raise UnsupportedRoofError(
            "mixed attachment needs one receiver and distinct leaf/end ports",
            issues=(GenerationIssue("junction", "mixed_arrangement"),),
        )
    if any(r.branch_width >= r.host_width - 4 * EPS for r in middles):
        raise UnsupportedRoofError(
            "mixed middle ports must be strictly narrower",
            issues=(GenerationIssue("junction", "branch_width"),),
        )
    host = next(iter(hosts))
    caps = [v.seed for v in primitives[host].vertices if v.role == "ridge_end"]
    vector = sub(caps[1], caps[0])
    length = math.hypot(*vector)
    direction = tuple(x / length for x in vector)
    coordinate = lambda p: sum(x * y for x, y in zip(sub(p, caps[0]), direction))
    bounds = sorted(coordinate(p) for p in (caps[0], caps[1]))
    slots = sorted(
        tuple(sorted(coordinate(d.vertices[i]) for i in r.shared)) for r in middles
    )
    conflict=any(a[1] + EPS >= b[0] for a,b in zip(slots,slots[1:]))
    for middle in middles:
        slot=tuple(sorted(coordinate(d.vertices[i]) for i in middle.shared))
        for terminal in terminals:
            near=coordinate(primitives[host].vertices[terminal.host_port].seed)
            at_start=abs(near-bounds[0])<EPS
            if ((middle.host_side-terminal.host_side)%4==2
                and terminal.branch_width < terminal.host_width-4*EPS):
                # A strictly lower shared corner on the opposite eave leaves
                # this slope's outer-corner hip at 45 degrees. The branch
                # ridge ends half its transverse width inward from its eave.
                # Its apex must lie strictly beyond that hip, in the same
                # receiving slope. This is an incidence applicability proof,
                # not a height solve or a sequential junction rewrite.
                apex=sum(slot)/2
                reach=middle.branch_width/2
                conflict |= (apex <= bounds[0]+reach+4*EPS if at_start
                             else apex >= bounds[1]-reach-4*EPS)
            else:
                reach=max(terminal.host_width,terminal.branch_width)
                blocked=(bounds[0],bounds[0]+reach) if at_start else (bounds[1]-reach,bounds[1])
                conflict |= slot[0]<blocked[1]+EPS and blocked[0]<slot[1]+EPS
    if conflict:
        raise UnsupportedRoofError(
            "mixed junction neighborhoods interact",
            issues=(GenerationIssue("junction", "interacting_slots"),),
        )
    return relations
