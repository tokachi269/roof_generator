# Polygon roof migration (1.4.0)

Orthogonal gable generation now constructs one continuous polygon roof rather
than composing a completed gable for each minimum rectangle. The minimum
partition and receiver regions provide exterior end/axis interpretations.
They do not prescribe internal roof junctions or final face ownership.

```text
Footprint -> region/axis guides -> compatible exterior end models
          -> PolygonRoof -> RoofGraph -> GeometryProblem -> fixed solve
          -> completed embedded pool -> seed -> mesh -> Blender
```

`PolygonRoof` is the topology authority: the actual polygon support and explicit
gable edges. Every other exterior edge remains an eave. A bounded, bundled
ordinary straight-skeleton implementation supplies global incidence. Oriented
terminal-cap disk replacement adds a boundary ridge end without relocating the
shared event or its other incident facets. Coplanar connected facets merge;
invalid cycles, missing support and unresolved events fail explicitly.

This is a terminal-gable model with possible hip facets, not a general delayed
wavefront or a proof that every rectangle guide's short end should be gabled.
Nonterminal/partial-edge gable intent remains outside this backend's domain.

## Authority and ranking

The earlier authority repairs made architectural relations explicit, but model
supports still followed fine rectangle boundaries. The causal comparison found
only 6/100 embeddings even with exhaustive small rectangle covers and both
axes. That disproved candidate discovery as the principal remaining limitation;
it did not disprove every rectangle-based roof method.

The new model produces no independent Cell roof primitives. Internal feature
inspection records source-eave facet incidence within the declared continuous
roof model. A relation label alone is not evidence for a roof junction.

Long axes are a componentwise prior, not a hard construction condition. End
sets and axis domains are considered together. Minimal required transverse
interpretations remain when long-axis interpretations have no compatible end
set. For each axis model, all maximal compatible gable end sets survive. No
area, valley-count or appearance score is used. Guide/source aliases receive
one topology identity and one seed probability mass. Incomplete sources/work
budgets prevent selection, including when a verified prefix exists.

These preference and compatibility rules are explicit project adaptations.
They are not presented as a complete published Hu/Laycock construction grammar.

## Geometry boundary

The solver receives a complete fixed graph. Skeleton event times and XYZ are
not anchors. The bundled implementation uses the core's intrinsic coordinate
frame for every input; it does not retry another scale or perturb a failed
event. GeometryProblem's explicit slope/anchor equations receive a necessary
linear feasibility check before nonlinear embedding. No graph or constraint
is changed by that check. Mesh validation remains independent.

The default orthogonal gable route does not call the old rectangle grammar
after failure. Other supported roof types and convex quadrilateral generation
retain their existing typed routes. Restricted member/port APIs remain
comparison tests, not fallback generators.

## Verified release evidence

- Full suite: 221 tests pass before the reporting-only budget classification repair;
  the additional focused audit test passes, including preserved old restricted-model proofs
  and migrated canonical authority/seed/mesh invariants.
- Installed ZIP operator: 13/13 representative cases, including four screenshot
  approximations, L/T/U/Cross, staircase, comb, Residential and Grid14/40.
- Installed addon smoke: four roof types, quad inputs, square seed variation,
  transforms, UV/material, failed-batch atomicity and footprint CLI pass.
- Runtime branch corpus: 100/100 mesh, preserving the previously supported
  branch family.
- Runtime structured: 100/103 mesh; nonuniform: 145/150 mesh. These are the
  normalized runtime results, not the prototype's 101/103 and 148/150.
- Installed ZIP corpus conversion: 145/145 core-success nonuniform and 100/100
  core-success structured roofs pass Blender mesh/UV/material validation. The
  other eight inputs were not attempted in Blender, not Blender failures.
- Runtime grid: all 1000 inputs attempted; 673 supported, 250 unsupported,
  77 incomplete (60 wall-budget censored, 16 cap work limits, one wavefront limit).
  Completed-prefix rates were never used as full coverage.
- Nonuniform outcomes: 145 supported, four unsupported, one incomplete.
  Structured outcomes: 100 supported, three unsupported, none incomplete.

The final ZIP and installed operator evidence match the recorded source hashes.
Completed runtime corpus and timing reports precede the invalid face-cycle
fail-fast guard; valid roof incidence is unchanged by that guard. The completed
grid run spans that guard addition and retains earlier timeouts as censored.
Source/evidence hashes and these scopes are recorded under
`authority/polygon/`. Blender images are native operator outputs, not simulated
core-only renders. Screenshot inputs approximate grid ratios; original user
mesh coordinates were not recovered.

## Performance and remaining limits

The post-migration benchmark measured warm medians of approximately 174 ms for
U, 1334 ms for Cross, 243 ms for Residential, 701 ms for Grid14 and 4538 ms for
Grid20. The fixture named Grid40 was an explicit unsupported event. These
samples overlapped the coverage job and are descriptive, not a controlled
speedup claim. First-call values and raw samples are preserved in the report.
Sub-second mass generation is not achieved for all supported inputs.

Unresolved simultaneous/antiparallel dependency events, finite end-model
coverage, large candidate pools and expensive unsuccessful embedding remain
limits. Timeout/work exhaustion is incomplete, not a negative roof-existence
proof. Nonorthogonal compound and new hip/shed families were not added.

The [paired cause diagram](authority/polygon/factory-causes.svg) shows minimum
Cells, historical separate roofs, declared continuous support and actual
installed-operator features for all four screenshot approximations. All internal
features identify their region and incident source-eave facets.

One profiled Grid20 generation spends 12.96 of 13.43 seconds in eight fixed
embeddings. Profiling overhead and concurrent jobs preclude comparing this to
unprofiled latency. It identifies embedding work rather than skeleton/candidate
discovery as the cost in that case; no new performance rewrite was made.

## Native base restoration (1.4.1)

The upstream-authoritative merge `3a47b78` removed the separately developed
`base_mesh.py` / `base_roof.py` and the Building panel. This was a migration
regression, not a missing Geometry Nodes editor context. Restored native bases
now call the current canonical `generate_footprint_mesh` API, not the removed
roof model. No dependency installer or fallback roof generator was restored.
Blender 5.2 modifier inputs use its typed RNA input values; 4.3–5.1 use the
existing ID-property API. The current backend marker invalidates saved legacy
roof caches.

The installed 1.4.1 ZIP verifies four analytic roof families, eight compound
shape differentials, a 16-building demo, height/roof toggles without unnecessary
cache regeneration, failed roofs preserving bases and walls, and clean
disable/re-enable handler registration. Roof surfaces match the canonical mesh
coordinates, faces and feature tags. Use View3D > Sidebar > Building > Create
Base Meshes.

The 1.4.0 operator/corpus evidence above remains a separate checkpoint. 1.4.1
changes the native-base adapter and UI; the polygon model/solver algorithm is
unchanged. Grid Blender conversion was not measured across all 1000 inputs.

The raw completed grid receipt counted one typed `WavefrontBudget` as
unsupported. `outcomes.json` corrects that classification to incomplete and
identifies the input; original raw measurements are preserved unchanged.
