# Roof generation architecture

The canonical pipeline is:

```text
Footprint
  -> decomposition candidates (minimum rectangles or one convex quad)
  -> ArchitecturalPart interpretations
  -> valid RoofGraph candidates
  -> stable seeded selection
  -> GeometryProblem
  -> validated embedding
  -> ordinary mesh
  -> Blender object
```

The distributable `addon/roof_generator/core/` owns generation. Host tools import
the same modules. Blender reads evaluated planar footprints and creates mesh
objects; it does not choose or repair topology.

Footprint analysis validates a hole-free simple polygon in its intrinsic frame.
Orthogonal inputs use exact minimum rectangular partition; a nonorthogonal convex
quad uses one Cell without a rectangular certificate. Other nonorthogonal
decompositions are explicitly unsupported. Minimum rectangle partition uses good diagonals, bipartite matching,
maximum independent sets and reflex completion. Each alternative has the same
minimum certificate. Architectural interpretation keeps compound members,
consumed cuts, exterior provenance, local axis/receiver options and published
evaluation terms. Canonical generation evaluates all completed interpretations;
published ranking is applied among valid topology candidates. Neither geometric Cell nor architectural unit implies one roof.

Topology composition consumes those member/port relations. It publishes only
complete disk graphs with boundary ownership, manifold links, roof-edge
semantics, a positive noncrossing drawing and a GeometryProblem. Rejected or
unimplemented relations are recorded separately. Incomplete candidate search
cannot select a winner. No algorithm substitutes for unsupported input.

Equivalent valid candidates are selected by stable namespaced seed digests and
geometry-based IDs. The orientation reference is a settings vector in the
footprint coordinate frame. Rotate it with the footprint for physical seed
equivariance, including perfectly symmetric shapes. Different random namespaces
do not consume a common PRNG stream.

Geometry solves fixed incidence; it cannot pick topology, roles or candidate
axes. Analytic rectangle embedding handles gable/hip/shed/flat. Compound topology
uses the Ren covariance planarity objective, explicit eave/pitch constraints and
fixed-variable nonlinear embedding. Convex quad gable has geometric directions
and equal-pitch boundary ports; nonparallel eaves can yield a sloping ridge.
No optimizer changes incidence or retries another architectural candidate. Mesh validation checks
fixed boundary, projection, shared vertices, positive faces and planarity.

Runtime core and Blender adapters require no external Python packages. Independent
development oracles may use NumPy/Shapely, declared separately from runtime.
See [the migration contract](python/docs/CANONICAL_MIGRATION.md) for the inventory
and [the research mapping](python/docs/ROOF_PART_INTERPRETATION_RESEARCH.md) for
published operations and their adaptation limits.

## Module responsibilities

```text
addon/roof_generator/
  core/
    footprint.py              normalization, scalar predicates, intrinsic frame
    partition.py              good diagonals, matching, completion, subdivision
    partition_candidates.py   bounded minimum candidate family and symmetry
    cells.py, provenance.py   Cell/Side/Adjacency and original boundary ownership
    architecture_models.py    architectural members, groups and relations
    architecture.py           resolved interpretation and Part ownership
    roof_ends.py              simultaneous roof-end and symmetry constraints
    architecture_selection.py published evaluation bounds and retained ties
    topology.py, junctions.py  primitives, ports and whole-arrangement junctions
    graph.py                  indexed RoofVertex/RoofFace/RoofEdge disk contract
    topology_candidates.py    valid alternatives, rejected relations and IDs
    seed.py                   independent stable digest namespaces
    generation.py             canonical orchestration and settings
    initialization.py         topology-preserving 2D coordinate initializer
    solve.py                  GeometryProblem, explicit constraints, exact embedding
    optimization.py           covariance objective and stdlib nonlinear embedding
    mesh.py                   fixed graph-to-mesh contract and validation
    errors.py                 UnsupportedRoofError
  mesh_frame.py, mesh_input.py planar source validation and coordinate transport
  blender_output.py           atomic ordinary object/material/UV output
  ui.py                       conversion settings and button
```

`Cell` is a geometric decomposition region. A minimum rectangle has its
certificate; a single convex quad does not claim that theorem.
`ArchitecturalMember` references a Cell with orthogonal local axes or geometric
directions; `ArchitecturalPart` groups members and records consumed
cuts. `PartRelation` describes architectural alternatives, while `AttachmentPort`
and `RoofConnection` describe implemented primitive incidences. None of these
units implies an independently capped final roof. `RoofVertex.seed` is its 2D
coordinate initializer, distinct from the integer/string generation seed.

`RoofFace.eaves` declares physical incident eave ownership. For a selected
eave-free slope fragment, `RoofFace.support` separately names an exterior eave
line of the same member. The composition template publishes it; GeometryProblem
uses that line for pitch constraints without adding an edge or changing a face
cycle. Missing support is unsupported, not inferred from a neighboring face.

## Candidate validity and selection

Composition receives a `ResolvedArchitecture`, including the selected member
directions, compatible global roof-end choices and their Part ownership.
Analytic corner contact admits shared/T choices rather than forcing a terminal
junction. One-line end constraints require coincident complete short ends;
staggered partial contacts remain `offset_continuation` unsupported. Decomposition is
retained for coordinates and provenance; it is not a roof parts list.
Compound composition binds declared combinations to graphless member port/cycle
templates, then assembles the final graph. `cell_primitives()` is a developer
inspection facility; production compound composition never generates Cell roofs.
Selected shared corner combinations require a local junction; Part grouping does
not by itself define a one-ridge roof. Internal continuation/parallel/partial-end
and inter-Part contacts are diagnosed separately and remain unsupported where no
architectural template has been specified. The solver does not choose templates.

Every internal feature in `Composition.features` records its declared member
axis/template or relation/operation cause at construction, plus Part ownership.
The graph and solver stay free of inspection metadata. Inspection exposes
architecturally preferred assignments, all constructible candidates and final
seedable ties separately. Adding an implementation can expand the selection set
without changing architectural scores; historical seeded output can consequently
change when the set expands.

Before adding nonorthogonal compound input, introduce decomposition backend
ownership: an orthogonal minimum-rectangle backend and a separate nonorthogonal
backend behind decomposition candidates. The current explicit convex-quad branch
does not justify proliferating polygon-type branches in `partition_candidates.py`.

The public coordinate entry points are `prepare_generation(points, settings)`
for the selected fixed-topology GeometryProblem and `generate_roof(points,
settings)` for a supported solved mesh. A `Generation` retains all valid ties
and rejected assignments for inspection. Developer tools can inspect earlier
stages independently, but no alternate runtime generation path exists.

The current seeded decision is the **joint valid roof candidate**, which includes
its minimum partition, member axes and implemented attachment interpretation.
It uses `derive(seed, "roof_candidate", candidate.id)` and selects the minimum
stable digest; this consumes no PRNG state. IDs are derived with BLAKE2b from
centered geometric keys, oriented face cycles, grouped Cell provenance and edge
roles. They omit incidental vertex numbers and source-input edge numbering.
`derive` also permits independent namespaces for additional decisions; material
randomization is not implemented. Core geometric IDs are quantized to a documented
numerical precision, not to an architectural grid.

Fully resolved published Hu evaluation terms rank VALID candidates. Equal scores
remain selectable. Undefined parallel/partial-end/continuation ports, unsupported
whole arrangements, self-crossing drawings and inconsistent incidence are
rejections. An exhausted partition or axis budget is incomplete, and cannot
publish a seeded winner. Seed never substitutes for an undefined operation.

Minimum candidate search is complete within its explicit family: all maximum
independent sets, both axes in canonical free-reflex order, plus exact footprint
symmetry images. It does not claim every possible reflex processing order. Every
materialized candidate still attains the classical minimum rectangle certificate.

## Embedding capabilities

Analytic embedding supports rectangle gable/hip/shed/flat and a single concave
flat face covering a hole-free orthogonal outline. Compound gable topology uses
published member port replacement for terminal/middle/noninterfering narrow
attachments, simultaneous distinct receiver-end terminal replacements, and two
opposite coincident equal-width ports. It does not flatten a
concave compound part into one primitive or leave internal caps/cuts in the graph.
The U fixture has one valid six-face compound graph. Residential and arbitrary
grid arrangements may have no implemented valid topology; the retained architectural interpretation and rejection reasons remain
inspectable. Multi-cell hip/shed and non-orthogonal compound decomposition are unsupported.

A GeometryProblem provides fixed face cycles, boundary anchors, internal XY/Z
variables and ridge directions. A receiver ridge with both exterior ports
consumed receives its equal-pitch height anchor from the declared opposite eaves;
its XY remains variable. Its initializer is not a solved mesh or a
nonlinear convergence certificate. The covariance nonlinear optimizer consumes
explicit eave/pitch constraints and validates convergence before mesh creation.
Mesh validation independently checks the unchanged face cycles and projection.
The adapter exports solved vertices, UVs, materials and provenance; it cannot
repair an invalid graph or a failed solve.

Rejections carry structured stage/code/member information. All independent local
relation blockers are reported for each assignment; downstream composition is
not run after a blocked relation. Diagnostic histograms are nonexclusive. A
building with valid alternatives may still have rejected assignments. The
read-only support audit streams details and distinguishes unsupported input from
incomplete-budget searches; it never interprets seed variation as missing rules.
