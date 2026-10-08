# Architectural authority audit

Baseline: `0210d7900c3a4340ddd5b22e05a673926332bbc7`.
This first audit changes no production algorithm.

| Stage | Actual input authority | Output | Architectural decision |
| --- | --- | --- | --- |
| Partition | Footprint and certified minimum search | Decompositions | No roof intent |
| Architecture | Member geometry and local combinations | ArchitecturalPartGraph and score intervals | Axes, receiver/branch, corner/continuation grouping |
| Topology candidate | Retained graph, member axes | Resolved Analysis, then Composition | Rejects continuation/parallel/partial_end even inside a Part |
| Junction planning | Decomposition adjacency and all Cell primitives | AttachmentPorts | Rediscovers end/side and receiver roles; never reads Parts or PartRelations |
| GeometryProblem | RoofGraph | Fixed incidence and embedding constraints | None |
| Solver | RoofGraph and GeometryProblem | Vertex embedding / RoofMesh | None; topology is fixed |

Observed call chain: `prepare_generation -> candidates -> recommend(defer_ranking=True)
-> build_candidates -> _resolved_analysis -> evaluate -> compose(d, axes)
-> cell_primitives(d, axes) -> plan(d, primitives) -> attachments(d, primitives)
-> _terminals/_middle -> problem -> solve -> RoofMesh`.

`topology_candidates.py` uses ArchitecturalPartGraph for scoring, IDs, coverage
validation and raw-cut exclusion, but does not pass it to composition.
`topology.py:compose` constructs one rectangle primitive for every Cell.
`junctions.py:attachments` rediscovers receiver roles from primitive caps/eaves
and raw adjacency. `_resolved_analysis` rejects all continuation contacts without
checking Part ownership. The authority-bypass hypothesis is therefore confirmed.

This does **not** yet establish that every surviving ridge or valley is spurious.
Supported terminal rewrites consume caps and explicitly create the junction hip,
valley and branch ridge; middle rewrites explicitly extend branch ridges and create
their valleys. A compound L-unit can legitimately have several member axes and
ridges. Part count alone is not an independent roof-feature oracle.

The successful factory-roof regression still needs a causal witness. Do not infer
the user's particular footprint or claim its repair from this audit. Neither raw
cut exclusion nor successful mesh validation proves architectural feature intent.

Ranking currently scores resolved assignments before composition, but only exposes
the best constructible alternatives. Architectural preference, constructibility and
the final seedable set need separate inspection.

The existing research mapping is in `ROOF_PART_INTERPRETATION_RESEARCH.md`.
Kada & McKinley section 2.4 explicitly reexamines neighbor configurations and replaces
junction blocks after fitting; its LiDAR-dependent choice is not a footprint-only
grammar. The Laycock URL returned HTTP 403 in this audit; its original was not
successfully reread. Prior repository research is evidence of previous interpretation,
not a substitute for successful access to that paper in this run.

Next boundary: resolved architecture owns member directions, Part ownership and
relations. Composition may validate an operation's applicability and use rectangle
incidence locally, but must not rediscover architectural relations from primitives.
Absorbing a relation into a Part is not permission to omit a required junction or
invent a continuation rewrite.
