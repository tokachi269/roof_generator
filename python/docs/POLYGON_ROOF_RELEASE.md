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

- Full suite: 221 tests pass, including preserved old restricted-model proofs
  and migrated canonical authority/seed/mesh invariants.
- Installed ZIP operator: 13/13 representative cases, including four screenshot
  approximations, L/T/U/Cross, staircase, comb, Residential and Grid14/40.
- Installed addon smoke: four roof types, quad inputs, square seed variation,
  transforms, UV/material, failed-batch atomicity and footprint CLI pass.
- Runtime branch corpus: 100/100 mesh, preserving the previously supported
  branch family.
- Runtime structured: 100/103 mesh; nonuniform: 145/150 mesh. These are the
  normalized runtime results, not the prototype's 101/103 and 148/150.
- Runtime grid 1000: bounded audit is still running. No completed-prefix rate
  is used as full coverage.

The final ZIP and installed operator evidence match the recorded source hashes.
Completed runtime corpus and timing reports precede the invalid face-cycle
fail-fast guard; valid roof incidence is unchanged by that guard. The ongoing
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
