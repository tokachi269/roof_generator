# SPDX-License-Identifier: GPL-3.0-or-later
"""Architectural interpretations to validated indexed topology alternatives."""

from dataclasses import dataclass, replace
from itertools import product
import math
from .errors import UnsupportedRoofError, GenerationIssue
from .solve import problem, GeometryProblem
from .initialization import _valid_drawing
from .architecture import Analysis
from .architecture_selection import evaluate
from .seed import derive, choose, point_identity
from .topology import compose, Composition, quadrilateral_graph
from .architecture_models import ArchitecturalPartGraph


@dataclass(frozen=True)
class TopologyCandidate:
    id: str
    architecture: ArchitecturalPartGraph
    axes: tuple[int, ...]
    composition: Composition
    geometry: GeometryProblem
    score: int

    def __post_init__(self):
        _validate(self.architecture, self.composition, self.geometry)

    @property
    def graph(self):
        return self.composition.graph


@dataclass(frozen=True)
class Rejection:
    partition: str
    axes: tuple[int, ...]
    reason: str
    issues: tuple[GenerationIssue, ...] = ()


@dataclass(frozen=True)
class TopologyCandidates:
    valid: tuple[TopologyCandidate, ...]
    rejected: tuple[Rejection, ...]
    complete: bool
    reason: str | None = None

    def select(self, seed=0):
        if not self.complete or not self.valid:
            detail = "; ".join(
                filter(None, (self.reason, *sorted({r.reason for r in self.rejected})))
            )
            raise UnsupportedRoofError("no selectable roof topology: " + detail)
        return choose(self.valid, seed, "roof_candidate", key=lambda c: c.id)


def _cell_id(d, cell, identity):
    return tuple(sorted(identity(d.vertices[v]) for v in cell.corners))


def partition_id(decomposition, reference_direction=(1, 0)):
    """Stable provenance join key for a minimum partition, also used by audits."""
    identity = point_identity(decomposition.footprint, reference_direction)
    return derive(
        0,
        "partition_id",
        tuple(
            sorted(_cell_id(decomposition, c, identity) for c in decomposition.cells)
        ),
    )


def _candidate_id(architecture, composition, axes, identity):
    d = architecture.decomposition
    cells = tuple(_cell_id(d, c, identity) for c in d.cells)
    graph = composition.graph
    keys = tuple((identity(v.seed), v.role) for v in graph.vertices)
    faces = []
    for face in graph.faces:
        ring = tuple(keys[i] for i in face.loop)
        faces.append(
            (
                min(ring[i:] + ring[:i] for i in range(len(ring))),
                tuple(sorted(cells[i] for i in face.cells)),
            )
        )
    edges = tuple(
        sorted(
            (tuple(sorted(keys[i] for i in e.vertices)), e.kind) for e in graph.edges
        )
    )
    groups = tuple(
        sorted(tuple(sorted(cells[c] for c in p.cells)) for p in architecture.parts)
    )
    return derive(
        0, "topology_id", (graph.roof_type, groups, tuple(sorted(faces)), edges)
    )


def _resolved_analysis(architecture, axes):
    relations = []
    issues = []
    reasons = []
    for relation in architecture.relations:
        assignment = tuple(axes[c] for c in relation.cells)
        options = tuple(o for o in relation.options if o.axes == assignment)
        if len(options) != 1:
            issues.append(
                GenerationIssue("relation", "unresolved_relation", relation.cells)
            )
            reasons.append(
                "member axis assignment does not resolve a unique local relation"
            )
        elif options[0].kind in {"parallel", "partial_end", "continuation"}:
            issues.append(GenerationIssue("relation", options[0].kind, relation.cells))
            reasons.append(
                "no published implemented port operation for " + options[0].kind
            )
        else:
            relations.append(replace(relation, options=options))
    if issues:
        # Record every independent local blocker. The first message is retained
        # for concise errors; diagnostics do not stop at the first relation.
        raise UnsupportedRoofError(reasons[0], issues=issues)
    # Reject undefined port relations before allocating a resolved member graph.
    # This changes no rejection rule, order, candidate or incidence.
    members = tuple(replace(m, axes=(axes[m.cell],)) for m in architecture.members)
    return Analysis(members, tuple(relations))


def _validate(architecture, composition, geometry):
    graph = composition.graph
    if set(c for f in graph.faces for c in f.cells) != {
        m.cell for m in architecture.members
    }:
        raise UnsupportedRoofError("roof topology loses member provenance")
    if geometry.faces != tuple(f.loop for f in graph.faces):
        raise UnsupportedRoofError("geometry problem changes topology")
    n = len(graph.vertices)
    if len(geometry.initial_vertices) != n or any(
        len(p) != 3 or not all(math.isfinite(x) for x in p)
        for p in geometry.initial_vertices
    ):
        raise UnsupportedRoofError("geometry problem has invalid initial coordinates")
    fixed = dict(geometry.fixed_z)
    if set(fixed).intersection(geometry.variable_z) or set(fixed).union(
        geometry.variable_z
    ) != set(range(n)):
        raise UnsupportedRoofError("geometry problem has incomplete height ownership")
    locations = {i for i, v in enumerate(graph.vertices) if v.boundary is not None}
    if set(geometry.variable_xy) != set(range(n)) - locations or any(
        geometry.initial_vertices[i][:2] != graph.vertices[i].seed for i in locations
    ):
        raise UnsupportedRoofError("geometry problem moves fixed footprint ownership")
    if not _valid_drawing(
        graph.outline,
        tuple(v.seed for v in graph.vertices),
        graph.faces,
        locations,
        {e.vertices: e.kind for e in graph.edges},
    ):
        raise UnsupportedRoofError(
            "roof graph has a crossing or zero-area initial drawing"
        )
    # Raw artificial partition segments are not roof edges. All final edges
    # already have explicit roof semantics and boundary ownership in RoofGraph.
    d = architecture.decomposition
    cuts = {
        frozenset(tuple(round(x, 10) for x in d.vertices[v]) for v in a.interval)
        for a in d.adjacency
    }
    for e in graph.edges:
        key = frozenset(
            tuple(round(x, 10) for x in graph.vertices[v].seed) for v in e.vertices
        )
        if key in cuts:
            raise UnsupportedRoofError("raw artificial cut leaked into roof topology")


def build_candidates(
    recommendation,
    roof_type="gable",
    *,
    reference_direction=(1, 0),
    pitch=0.5,
    eave_height=0,
    max_axis_assignments=4096
):
    """No unsupported combination ever reaches seeded selection.

    Incidence operations inspect member ports of a compound unit, not its box.
    Unresolved contacts reject only their assignment. Unfinished searches have
    no winner. Successful 2D topology/problem conversion does not claim a solved
    nonlinear embedding.
    """
    if (
        recommendation.search.candidates
        and not recommendation.search.candidates[0].footprint.orthogonal
    ):
        return _quadrilateral_candidates(
            recommendation, roof_type, reference_direction, pitch, eave_height
        )
    if max_axis_assignments < 1:
        raise ValueError("axis-assignment budget must be positive")
    if not recommendation.search.complete:
        return TopologyCandidates((), (), False, recommendation.search.reason)
    valid = {}
    rejected = []
    work = 0
    for _, architecture in recommendation.retained:
        d = architecture.decomposition
        identity = point_identity(d.footprint, reference_direction)
        partition_key = partition_id(d, reference_direction)
        assignments = (
            product(*(m.axes for m in architecture.members))
            if roof_type == "gable"
            else ((),)
        )
        for axes in assignments:
            if work >= max_axis_assignments:
                return TopologyCandidates(
                    tuple(valid[k] for k in sorted(valid)),
                    tuple(rejected),
                    False,
                    "topology axis-assignment budget exhausted",
                )
            work += 1
            stage = "relation"
            try:
                if roof_type == "gable":
                    resolved = _resolved_analysis(architecture, axes)
                    evaluation = evaluate(d, resolved, recommendation.policy)
                    if evaluation.score[0] != evaluation.score[1]:
                        raise UnsupportedRoofError(
                            "resolved axes still have an uncertain evaluation"
                        )
                    score = evaluation.score[0]
                else:
                    score = 0
                shed_edge = None
                if roof_type == "shed" and len(d.cells) == 1:
                    # The declared reference frame fixes directional intent;
                    # cyclic vertex order cannot reverse the low eave.
                    u = reference_direction
                    rise = (-u[1], u[0])
                    world = tuple(
                        d.footprint.frame.world_xy(p) for p in d.footprint.vertices
                    )
                    shed_edge = max(
                        range(4),
                        key=lambda i: (
                            -(world[(i + 1) % 4][1] - world[i][1]) * rise[0]
                            + (world[(i + 1) % 4][0] - world[i][0]) * rise[1]
                        )
                        / math.dist(world[i], world[(i + 1) % 4]),
                    )
                stage = "composition"
                composition = compose(
                    d, roof_type, axes=axes or None, shed_edge=shed_edge
                )
                stage = "geometry_problem"
                geometry = problem(
                    composition.graph, pitch, eave_height / d.footprint.frame.scale
                )
                stable_id = _candidate_id(architecture, composition, axes, identity)
                stage = "graph_validation"
                valid.setdefault(
                    stable_id,
                    TopologyCandidate(
                        stable_id, architecture, axes, composition, geometry, score
                    ),
                )
            except UnsupportedRoofError as exc:
                issues = exc.issues or (GenerationIssue(stage, "unsupported"),)
                rejected.append(Rejection(partition_key, axes, str(exc), issues))
    # Published terms are applied to fully resolved choices. No aesthetic score
    # resolves ties; all equally ranked VALID alternatives remain seedable.
    best = max((c.score for c in valid.values()), default=None)
    retained = tuple(valid[k] for k in sorted(valid) if valid[k].score == best)
    return TopologyCandidates(
        retained,
        tuple(rejected),
        True,
        (
            None
            if retained
            else "all architectural assignments lack a valid implemented roof topology"
        ),
    )


def _quadrilateral_candidates(
    recommendation, roof_type, reference_direction, pitch, eave_height
):
    """One geometric member, no orthogonal-axis or rectangle scoring assumption."""
    valid = {}
    rejected = []
    for _, architecture in recommendation.retained:
        fp = architecture.decomposition.footprint
        identity = point_identity(fp, reference_direction)
        partition_key = partition_id(architecture.decomposition, reference_direction)
        if roof_type == "gable":
            eaves = (0, 1)
        elif roof_type == "shed":
            u = reference_direction
            rise = (-u[1], u[0])
            world = tuple(fp.frame.world_xy(p) for p in fp.vertices)
            eaves = (
                max(
                    range(4),
                    key=lambda i: (
                        -(world[(i + 1) % 4][1] - world[i][1]) * rise[0]
                        + (world[(i + 1) % 4][0] - world[i][0]) * rise[1]
                    )
                    / math.dist(world[i], world[(i + 1) % 4]),
                ),
            )
        else:
            eaves = (0,)
        for eave in eaves:
            try:
                graph = quadrilateral_graph(fp, roof_type, eave=eave)
                composition = Composition(graph, (), ())
                geometry = problem(graph, pitch, eave_height / fp.frame.scale)
                stable_id = _candidate_id(architecture, composition, (), identity)
                valid[stable_id] = TopologyCandidate(
                    stable_id, architecture, (), composition, geometry, 0
                )
            except UnsupportedRoofError as exc:
                rejected.append(
                    Rejection(
                        partition_key,
                        (),
                        str(exc),
                        (GenerationIssue("composition", "unsupported"),),
                    )
                )
    return TopologyCandidates(
        tuple(valid[k] for k in sorted(valid)),
        tuple(rejected),
        recommendation.search.complete,
        None if valid else "no valid nonorthogonal primitive",
    )
