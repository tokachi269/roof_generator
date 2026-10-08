# SPDX-License-Identifier: GPL-3.0-or-later
"""Architectural interpretations to validated indexed topology alternatives."""

from dataclasses import dataclass, replace
from itertools import product
import math
from .errors import UnsupportedRoofError, GenerationIssue
from .solve import problem, GeometryProblem
from .initialization import _valid_drawing
from .architecture import resolve
from .architecture_selection import evaluate
from .seed import derive, choose, point_identity
from .topology import compose, Composition, quadrilateral_graph, primitive_composition
from .architecture_models import ArchitecturalPartGraph
from .roof_ends import RoofEnds, roof_configurations


@dataclass(frozen=True)
class TopologyCandidate:
    id: str
    architecture: ArchitecturalPartGraph
    axes: tuple[int, ...]
    composition: Composition
    geometry: GeometryProblem
    score: int
    ends: RoofEnds | None = None

    def __post_init__(self):
        _validate(self.architecture, self.composition, self.geometry, self.axes)
        if self.ends is not None:
            # A candidate is a public immutable record; reject forged end
            # states as well as a connection that uses the wrong operation.
            resolve(self.architecture, self.axes).with_ends(self.ends)
            decisions = {j.cells: j.kind for j in self.ends.joints}
            for connection in self.composition.connections:
                cells = tuple(sorted((connection.host, connection.branch)))
                expected = "shared" if connection.kind == "terminal" else "extension"
                if decisions.get(cells) != expected:
                    raise UnsupportedRoofError("roof connection contradicts resolved end configuration")

    @property
    def graph(self):
        return self.composition.graph


@dataclass(frozen=True)
class Rejection:
    partition: str
    axes: tuple[int, ...]
    reason: str
    issues: tuple[GenerationIssue, ...] = ()
    end_choices: tuple = ()


@dataclass(frozen=True)
class ArchitecturalChoice:
    partition: str
    axes: tuple[int, ...]
    score: int
    end_choices: tuple = ()


@dataclass(frozen=True)
class TopologyCandidates:
    valid: tuple[TopologyCandidate, ...]
    rejected: tuple[Rejection, ...]
    complete: bool
    reason: str | None = None
    architectural: tuple[ArchitecturalChoice, ...] = ()
    constructible: tuple[TopologyCandidate, ...] = ()

    def inspect_ranking(self):
        best = max((c.score for c in self.architectural), default=None)
        return {
            "architectural_preferred_assignments": [c.__dict__ for c in self.architectural if c.score == best],
            "architectural_assignment_count": len(self.architectural),
            "constructible_candidate_ids": [c.id for c in self.constructible],
            "selectable_candidate_ids": [c.id for c in self.valid],
            "complete": self.complete,
            "selection_rule": "best architectural score among constructible candidates, then seed",
        }

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



def _validate(architecture, composition, geometry, axes):
    graph = composition.graph
    owners = {c: p.id for p in architecture.parts for c in p.cells}
    relations = {r.cells: r for r in architecture.relations}
    for feature in composition.features:
        if feature.parts != tuple(sorted({owners[c] for c in feature.members})):
            raise UnsupportedRoofError("feature cause changes architectural part ownership")
        if feature.relation is not None:
            relation = relations.get(feature.relation)
            kinds = {"corner"} if feature.operation == "terminal" else {"corner", "side_attachment"}
            if (relation is None or len(relation.options) != 1 or relation.options[0].kind not in kinds
                or relation.options[0].axes != tuple(axes[c] for c in relation.cells)):
                raise UnsupportedRoofError("feature cause is absent from architectural relations")
            if not any(tuple(sorted((c.host, c.branch))) == feature.relation and c.kind == feature.operation for c in composition.connections):
                raise UnsupportedRoofError("feature cause lacks its declared roof connection")
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
    architectural = []
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
                    tuple(architectural),
                    tuple(valid[k] for k in sorted(valid)),
                )
            work += 1
            stage = "relation"
            score = None
            try:
                if roof_type == "gable":
                    resolved = resolve(architecture, axes)
                    evaluation = evaluate(d, resolved.analysis(), recommendation.policy)
                    if evaluation.score[0] != evaluation.score[1]:
                        raise UnsupportedRoofError(
                            "resolved axes still have an uncertain evaluation"
                        )
                    score = evaluation.score[0]
                else:
                    score = 0
                    resolved = resolve(architecture, tuple(m.axes[0] for m in architecture.members))
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
                configs = roof_configurations(resolved, evaluation.symmetry) if roof_type == "gable" else (None,)
                found = False
                for index, ends in enumerate(configs):
                    found = True
                    if index:
                        if work >= max_axis_assignments:
                            return TopologyCandidates(tuple(valid[k] for k in sorted(valid)), tuple(rejected), False,
                                "roof end-configuration budget exhausted", tuple(architectural), tuple(valid[k] for k in sorted(valid)))
                        work += 1
                    authority = resolved.with_ends(ends) if ends is not None else resolved
                    architectural.append(ArchitecturalChoice(partition_key, tuple(axes), score,
                        tuple((j.cells, j.kind) for j in ends.joints) if ends else ()))
                    try:
                        stage = "composition"
                        composition = compose(authority, roof_type, shed_edge=shed_edge)
                        stage = "geometry_problem"
                        geometry = problem(composition.graph, pitch, eave_height / d.footprint.frame.scale)
                        stable_id = _candidate_id(authority.architecture, composition, axes, identity)
                        stage = "graph_validation"
                        valid.setdefault(stable_id, TopologyCandidate(
                            stable_id, authority.architecture, axes, composition, geometry, score, ends))
                    except UnsupportedRoofError as exc:
                        issues = exc.issues or (GenerationIssue(stage, "unsupported"),)
                        rejected.append(Rejection(partition_key, axes, str(exc), issues,
                            tuple((j.cells, j.kind) for j in ends.joints) if ends else ()))
                if not found:
                    raise UnsupportedRoofError("all roof end configurations violate simultaneous constraints",
                        issues=(GenerationIssue("architecture", "end_conflict"),))
            except UnsupportedRoofError as exc:
                if score is not None:
                    architectural.append(ArchitecturalChoice(partition_key, tuple(axes), score))
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
        tuple(architectural),
        tuple(valid[k] for k in sorted(valid)),
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
                composition = primitive_composition(graph)
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
        (),
        tuple(valid[k] for k in sorted(valid)),
    )
