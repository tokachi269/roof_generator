# Canonical generation migration

Baseline: `121533dd6f1152f1bd46d80493b00e7ea84d1783`.
This inventory and contract are fixed before algorithm changes.

## Inventory

| Existing owner | Classification | Migration |
| --- | --- | --- |
| `python/graph_first/footprint.py` | Canonical scalar outline analysis | Move unchanged into addon core; no polygon-library owner. |
| `rectangle_partition.py`, `cells.py`, `partition_candidates.py` | Canonical minimum partition and alternatives | Preserve certificate/family, then profile shared versus candidate-local work. |
| `parts.py`, `part_interpretation.py`, `part_selection.py` | Canonical architectural interpretation | Explicit architectural names; keep local member relations, unresolved contacts and published score bounds. |
| `graph.py`, `topology.py`, `connections.py` | Canonical indexed graph and scoped published junctions | Add valid candidate assembly from architecture; then move to core. |
| `geometry.py` | Initialization, geometry problem, mesh validation and analytic rectangle solve mixed together | Split initialization, solve and solved mesh responsibility without changing algorithms. |
| `addon/roof_generator/core/roof_{building,geometry,parts,partition,planes,graph,connections,features,mesh,validation}.py` | Old production, duplicated graph/part semantics, support-plane topology discovery and NumPy/Shapely dependency owners | Remove after canonical API and adapter cutover. No runtime fallback or retained import oracle. |
| `addon/roof_generator/{mesh_frame,mesh_input,blender_output,ui}.py` | Blender adapter, mixed old geometry and dependency assumptions | Scalar source-mesh validation and transport, canonical request API; no topology repair. |
| `dependencies.py`, `install_roof_dependencies.py`, `requirements-roof.txt` | Old binary dependency installation/compatibility | Remove when adapters no longer need NumPy/Shapely. |
| `inspect_*`, `benchmark_*` | Evaluation/debug and measurement utilities | Keep responsibility-specific tools; consolidate redundant generation benchmarks and inspection APIs. |
| `roof_harness.py`, `tests/graph_first_reference.py` | Secondary semantic snapshot and transitional type adapter | Keep useful frozen expectations; migrate to indexed graph/mesh observations; delete old generator imports and fake old model. |
| `tests/test_roof_acceptance.py`, `test_partition_{search,grid}.py`, `test_dependencies.py` | Mix of semantic evidence and old implementation/dependency assertions | Preserve inputs and useful static expectations; replace obsolete implementation assertions with canonical invariants and explicit unsupported proofs. |
| `tests/grid_footprints.py`, fixture JSON, independent Shapely/NumPy checks | Test generators and independent oracles | Retain outside runtime; separate development requirements. |
| `build_addon.py`, `packages/`, CI and Blender smoke tools | Packaging and deployment evidence | Package only canonical source; smoke without wheel/pip installation. |
| Older design/evaluation documents and diagrams | Historical evaluations | Move relevant history away from main architecture; remove obsolete command/API documentation. |

## Target ownership

One distributable core under `addon/roof_generator/core/`, used by host tools
and Blender alike. Responsibilities: footprint, minimum partition/cells and
candidates, architectural models/interpretation/evaluation, indexed RoofGraph,
primitive/junction topology, topology candidates, namespaced seed, initialization,
GeometryProblem/solve, solved mesh, generation entry point. No compatibility
aliases, copied second core or old/new public generators remain after cutover.

Names distinguish `Cell`, `ArchitecturalPart`, `PartRelation`, `PartCombination`,
`RoofFace`, `RoofVertex`, `RoofEdge`, `RoofConnection`, `TopologyCandidate` and
`GenerationSettings`. A compound architectural unit retains members/relations;
it is never automatically one primitive.

## Candidate and seed contract

Generate candidate topology only from retained minimum architectural
interpretations and compatible member-axis assignments. Resolve shared axis
assignments consistently across all incident relations. Unimplemented relations,
invalid incidence/drawing and incomplete searches are rejected with inspectable
reasons, not seeded alternatives. Validate one boundary, disk/link incidence,
fixed exterior ownership, positive/noncrossing XY drawing, semantics and
GeometryProblem conversion before publishing a candidate. A geometry problem is
not a completed nonlinear solve or a proof of solver convergence.

Seed selection occurs only after that gate. Stable BLAKE2-derived namespaces and
geometry-based candidate IDs replace enumeration order and Python `hash()`.
Selection ranks candidates by derived digest; no sequential PRNG consumption.
Unrelated namespaces cannot alter roof decisions. No new aesthetic weights.

Perfect symmetry requires an orientation reference for a physical seeded choice:
a rotation that leaves a Cross unchanged cannot both leave a unique horizontal
choice unchanged and map it to vertical. `reference_direction` is therefore an
explicit settings vector; translate/rotate footprint and this vector together
for physical equivariance. The default is the supplied coordinate frame's X
axis. Blender supplies its footprint-local frame. Winding/cyclic changes never
change that vector. This is symmetry breaking by declared input, not matching
order as an architectural preference.

## Research mapping and initial rule boundary

Reuse Hu Sections 3.4–3.5 end/side and compound member constraints, Sugihara's
local narrow/wide attachment and the already proved terminal/middle splice.
Kada Section 2.4/Fig. 8–11 permits neighbor-arrangement junction replacement;
an aligned pair of opposite equal-width middle ports can share one junction,
with four ridges and four reflex valleys instead of coincident independent
T-junctions. Implement that indexed incidence only with exact port/slot
compatibility and an independent planar witness. Do not generalize arbitrary
interacting branches from it. U/Residential/Grid membership alone is never a
rule. Retained interpretation issues without a supported port operation remain
unsupported, including unproved compound realizations.

## Sequence and evidence

1. Inventory/contract (this commit; no production edits).
2. Namespaced seed and independent reproducibility proofs.
3. Architecture-to-valid-topology candidates, explicit rejects; supported shared
   junction operation in a separate algorithm commit.
4. Type naming, mechanical module moves and import migration separately.
5. Canonical generation and Blender cutover; remove old production/dependencies,
   migrate useful static/invariant proofs and current README/API docs.
6. Profile before optimizing; preserve candidate/retained/seed signatures exactly.
7. Stage before/after and 1,000-building measurements, package/Blender/CI proof.

Existing nonlinear optimization is not silently resurrected. Rectangle analytic
embedding remains; unsupported compound solves fail before Blender scene mutation.
The new scope can expose more topology than final-mesh cases. Main documentation
must clearly state that boundary instead of presenting problem generation as a
solved mesh.
