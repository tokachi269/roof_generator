# SPDX-License-Identifier: GPL-3.0-or-later
"""Migrate fixed-partition legacy oracles to explicit architecture inputs.

The historical primitive orientation is only test input setup. Production never
uses these wrappers or infers architectural intent from generated primitives.
"""

from roof_generator.core.architecture import interpret, resolve
from roof_generator.core.topology import cell_primitives, compose as compose_resolved
from roof_generator.core.junctions import plan as plan_resolved, attachments as bind


def authority(d, axes=None, primitives=None):
    architecture = interpret(d)
    if axes is None:
        primitives = primitives or cell_primitives(d)
        axes = []
        for primitive in primitives:
            ends = [v.seed for v in primitive.vertices if v.role == "ridge_end"]
            axes.append(int(abs(ends[1][1] - ends[0][1]) > abs(ends[1][0] - ends[0][0])))
    if any(a not in m.axes for a, m in zip(axes, architecture.members)):
        from roof_generator.core.errors import UnsupportedRoofError
        raise UnsupportedRoofError("fixed primitive orientation is outside architectural member domain")
    return resolve(architecture, axes)


def compose(d, roof_type="gable", *, axes=None, shed_edge=None):
    return compose_resolved(authority(d, axes), roof_type, shed_edge=shed_edge)


def plan(d, primitives):
    return plan_resolved(authority(d, primitives=primitives), primitives)


def attachments(d, primitives):
    return bind(authority(d, primitives=primitives), primitives)

# Historical explicit port fixtures: only exercise the local rewrite oracle.
from collections import defaultdict
import math
from roof_generator.core.footprint import EPS, on_segment, sub
from roof_generator.core.errors import UnsupportedRoofError, GenerationIssue
from roof_generator.core.junctions import port, _mixed_plan, AttachmentPort
def fixed_port_fixture(decomposition, primitives):
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


def operation_composition(d):
    from roof_generator.core.topology import _middle, _terminals
    primitives = cell_primitives(d)
    relations = fixed_port_fixture(d, primitives)
    return (_terminals if any(r.kind == "terminal" for r in relations) else _middle)(d, primitives, relations)
