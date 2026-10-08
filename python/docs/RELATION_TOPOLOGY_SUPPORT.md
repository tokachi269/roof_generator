# Relation-to-topology support

## Scope and measurement

The primary result is a valid 2D RoofGraph and its GeometryProblem, not a solved
compound mesh. `audit_roof_support.py` records **every rejected assignment** and
all independent relation blockers in that assignment. Nonexclusive building
incidence, rejected-assignment incidence and relation occurrences have different
denominators. Downstream junction/embedding failures remain unobserved when a
relation blocks composition. A sole known blocker is only a conditional upper
bound on future support, never a prediction that removing it makes a roof valid.

The previous 833/1000 unsupported batch repeats six fixed outlines. A separate
corpus contains 1000 unique seeded connected-grid outlines, scaled to 3 metre
units. It is a synthetic coverage probe, not a housing-distribution estimate.
The same saved corpus is replayed before and after the operation change.

## Published mechanisms and applicability

| Relation | Published mechanism | Current indexed-graph consequence |
| --- | --- | --- |
| continuation | Laycock/Day 2003 §7 Fig 6 case 2: merge compatible models with collinear exterior edges; Hu/Fan/Noskov 2017 §3.4.1, Figs 12–13: eliminate triangular end caps at adjacent short ends | Specifies cap constraints, **not** the complete incidence for offset or stepped-width end contacts |
| terminal branch | Hu §3.4.3, Figs 15–18: shared corner junction or T combination; intersect all constraints imposed on an end. Laycock/Day 2003 §7 Fig 6 case 1: attached branch. Sugihara/Hayashi 2007 pp.312–313 Figs 4–6: narrow branches extend toward the wider receiving roof | Consume host near port and branch near cap; share ridge/valley/outer hip incidence; unequal width refines into two trivalent joints |
| multiple terminal branches | Sugihara Figs 5–6 demonstrate multiple branches on a main roof; Hu Fig 18 forbids choosing end combinations independently of other constraints | Recognize **all** ports first; permit replacements at distinct host ends only; rewrite host cycles once, not sequential pairwise merging |
| partial end | Hu end constraints do not specify arbitrary incomplete end/side incidence | Remains unsupported; a cap constraint alone is not a junction graph |
| parallel | Hu §3.3 rule 2 discourages adjacent long-side roof pairs to avoid narrow spaces | Partition ranking is available; this is not a published roof-connection template |
| interacting junctions | Kada/McKinley 2009 §2.4, Fig 11 replaces corner/T/cross blocks using compatible neighboring fitted roof parameters | Arbitrary overlap is not justified by footprint-only matching; existing equal-width opposite cross remains the restricted compatible case |

Primary sources were reread, including Hu §§3.3–3.5 and the original Sugihara
p.313 figure/text. Detailed source URLs and the earlier complete comparison are
in [ROOF_COMPOSITION_RESEARCH.md](ROOF_COMPOSITION_RESEARCH.md).

### Why continuation is not automatically a simple merge

If two nonoverlapping minimum rectangular cells have equal transverse bounds
and adjacent full ends, their union is one rectangle. Replacing them by that
rectangle preserves coverage and reduces the count, contradicting the minimum
certificate. Therefore aligned equal-width full-end continuation between such
cells cannot be the missing operation. The actual `continuation` vocabulary
includes offset and width-step end contacts. Hu's rule removes end triangles,
but does not determine their junction incidence. Implementing plain ridge
continuation for those contacts would claim support without a topology rule.
The audit separately checks this geometric distinction.

## Multi-terminal operation contract (before implementation)

This is a constrained **graph adaptation** of published branch extension and
shared corner incidence; neither paper supplies this exact indexed algorithm.
It reuses the existing proved single-terminal operation rather than claiming an
arbitrary new junction grammar.

1. Relations identify one receiver and distinct exterior-leaf branches, covering
   every member. All attachments are terminal, with perpendicular primitive axes.
2. Each consumed host end is distinct. The receiver is a geometric side role, not a global higher main roof.
   Each end uses the established single-terminal local wider/narrower
   refinement; either neighbor may be wider, independently of the other end. Mixed terminal/middle or two replacements on one end fail.
3. Allocate surviving exterior gable ports and a corner junction per attachment.
   Remove all consumed host ports, branch caps and artificial boundaries. Rewrite
   each host face using the full attachment set once; branch faces splice into
   that cycle. Equal-width joints have ridge/ridge/hip/valley incidence. Unequal
   joints split into high(host ridge/outer hip) and low(branch ridge/reflex valley)
   joined by a hip. The host ridge connects retained ports/joints once.
4. Distinct local replacements are disjoint cycle neighborhoods; each internal
   spoke has two opposite face incidences. Replacing a vertex by one vertex or
   a two-vertex path preserves disk links. The final RoofGraph validates links,
   one exterior boundary, Euler disk and complete exterior/member provenance.
5. Only after incidence is fixed, initialize XY along **declared primitive axes**.
   Internal-to-internal host ridge edges no longer require an exterior cap.
   Local high/low pairs may backtrack toward their axis intersection together;
   that coincident limit is never emitted. A crossing/degenerate drawing fails.
   No XYZ, plane envelope, Boolean, wavefront or optimizer selects incidence.
6. Primary tests supply independent planar metric witnesses for opposite-end
   attachments with narrower, equal and wider branches. Hu’s simultaneous end
   constraints do not justify a global wider-host restriction; Sugihara’s higher
   roof distinction is local to each connection. Keeping that distinction local
   is necessary for the existing slightly-wider-branch U fixture. Also verify input transforms, cyclic start, winding,
   collinear redundancy and relation-order permutations. Witness geometry is a
   test oracle, not production topology discovery or a fixture special case.

This operation does not imply interacting-junction, continuation, partial-end,
parallel-contact or arbitrary generated-grid support. It does not add a
nonlinear geometry solver or a Blender compound-mesh fallback.

## Baseline findings

See [canonical/support_before.json](canonical/support_before.json). The unknown
corpus has 2 supported, 986 unsupported and 12 incomplete-budget buildings.
Unsupported-building incidence: parallel 981, continuation 790, partial_end 790;
these counts overlap. All 284,324 continuation occurrences have width-step or
axis-offset bounds; zero are the trivial aligned full-end merge. Conditional
sole-known-blocker incidence is parallel 777, partial_end 61, continuation 38,
terminal arrangement 36. These upper bounds censor downstream failures.

The original U receiver is slightly narrower than both branches. A rule that
rejects this only because the geometric receiver is not the locally wider roof
would be more restrictive than the existing singleton terminal contract. The
multi-terminal extension must prove all local width orderings using independent
planar witnesses, while keeping distinct-end/leaf and noncrossing applicability.

## GeometryProblem height ownership

Removing both receiver caps also removes its exterior ridge-height anchor.
`solve.problem` supplies the missing height from the two declared opposite eaves
of its incident slopes: for equal pitch p and eave separation w, the ridge rise
is p*w/2. Internal XY stays variable and ridge directions stay fixed; no final XY
or topology is determined here. The independent width-ordering witnesses check
these fixed heights as well as the unchanged face cycles. This is a solve-input
constraint, not an SGA21 solver, roof-plane envelope or topology operation.

## Results

Start: `f3287e5f09a0dafd0ac1702b43481da97f4103d1`. Topology operation:
`89000b1`. GeometryProblem height-anchor correction: `a7f4b60`.
Full corpus diagnostics compare the baseline with the topology operation; the
subsequent height-anchor tests preserve those valid topology candidates.

| Corpus (gable Graph/GeometryProblem, not meshes) | Before supported / unsupported / incomplete | After |
| --- | --- | --- |
| Six fixed fixtures repeated 1000 times | 167 / 833 / 0 | 334 / 666 / 0 |
| 1000 unique unknown connected-grid outlines | 2 / 986 / 12 | 3 / 985 / 12 |

The unknown corpus contains 6–40 vertices, seed 92821, 3m grid units, and is frozen
in [support_grid.json.gz](canonical/support_grid.json.gz). Its decompressed SHA256
is `50fdc2041478650e165efea5ea2089e8e176635aa7b6e66dd04e3a438562479c`.
This is coverage testing, not a claim about the frequency of actual house roofs.

| Cause on unsupported unknown buildings | Before building incidence | Before rejected-assignment incidence | Before issue occurrences | After building incidence |
| --- | ---: | ---: | ---: | ---: |
| parallel | 981 | 277075 | 1502054 | 980 |
| partial_end | 790 | 193030 | 334180 | 789 |
| continuation | 790 | 182412 | 284324 | 789 |
| terminal arrangement | 36 | 85 | 85 | 35 |
| host arrangement | 16 | 21 | 21 | 16 |
| equal-width ports | 2 | 2 | 2 | 2 |
| branch width | 1 | 1 | 1 | 1 |
| interacting slots | 1 | 1 | 1 | 1 |

The assignment/occurrence columns include rejected assignments from supported
and incomplete buildings as well. They are nonexclusive, and never sum to a
building total. All independent local blockers are observed; later junction
failures behind those blockers are censored. The conditional sole-known-blocker
counts (777 parallel, 61 partial_end, 38 continuation, 36 terminal arrangement)
therefore do **not** forecast actual successful roofs.

The U fixture retains one valid candidate from two architectural interpretations:
6 slope faces, 3 ridge edges, 2 valleys and 4 hips. Both receiver end caps and
artificial partition cuts are consumed. Its main ridge connects internal joints,
not exterior gable ports. See [U inspection](canonical/u.json) and
[U Graph diagram](canonical/u-candidate-0.svg). The remaining interpretation is
explicitly rejected. Receiver is a side/port role; the two locally wider neighbors
retain their higher ridge junctions. There is no global largest-area main rule.

The newly supported unknown case is [generated_0024](canonical/generated-0024.json),
an 8-vertex offset outline, with [its unified Graph](canonical/generated-0024.svg).
It uses exactly the same distinct-end operation; no shape label is inspected.
The other fixed Residential/Grid14/Grid20/Grid40 cases remain unsupported for
gable topology. Cross keeps its two valid seedable architectural alternatives.

Across the frozen unknown corpus, minimum partition counts, retained interpretation
counts and completeness flags are unchanged. No previously supported case was
lost. The two original unknown successes retain their full family/seed fingerprint.
The topology-operation snapshot records 985 unchanged full fingerprints; differences are the new valid case and
clarified terminal-arrangement messages. Rectangle/L/T/Cross candidate IDs and
seed 0–15 choices are frozen independently in
[seed_topology_reference.json](../tests/fixtures/seed_topology_reference.json).
Transforms, winding, cyclic start, collinear redundancy and adjacency order retain
physical seed choice. No Shapely/NumPy is used by the runtime; independent planar
witness coverage in tests uses those development oracles.

## Performance and reproducibility

[Before stage timings](canonical/support_performance_before.json) and
[after stage timings](canonical/support_performance_after.json) use two warmups
and nine unprofiled calls to `benchmark_generation.measure` on the same inputs.
Each seed-selection stage samples four seeds. These are observations, not an
optimization claim; this series increases operation support and diagnostics.

| Case | Partition candidates before → after (ms) | RoofGraph + problem before → after (ms) | Total before → after (ms) |
| --- | ---: | ---: | ---: |
| rectangle_gable | 0.462 → 0.536 | 0.714 → 0.696 | 1.559 → 1.500 |
| orthogonal_L | 1.379 → 1.282 | 4.753 → 4.338 | 6.637 → 6.029 |
| orthogonal_T | 1.578 → 1.110 | 3.110 → 2.351 | 4.752 → 4.152 |
| orthogonal_U | 3.634 → 5.334 | 2.524 → 8.361 | 7.182 → 17.057 |
| cross | 2.822 → 5.344 | 8.621 → 18.564 | 12.760 → 26.475 |
| residential_multi_reflex | 5.293 → 9.739 | 1.308 → 3.100 | 8.354 → 14.204 |
| grid_14 | 15.437 → 13.253 | 3.138 → 3.059 | 25.059 → 21.903 |
| grid_20 | 27.090 → 25.602 | 2.823 → 2.467 | 42.756 → 36.086 |
| grid_40 | 183.181 → 138.839 | 48.646 → 38.340 | 300.052 → 232.153 |

Final stage samples include the receiver-height-anchor correction. The separate existing [1000-building benchmark before](canonical/support_benchmark_before.json)
and [after](canonical/support_benchmark_after.json) measure the repeated six-fixture
batch, not 1000 unique random shapes. The final status counts are as above.
Benchmark clocks are taken before the final receiver-height-anchor correction;
that correction only adds solve-input constraints and its planar witnesses.
The all-detail diagnostic runs retained too much memory to be useful latency
measurements; the audit now streams details and aggregates immediately. Their
support/cause counts are unchanged. Do not infer a speedup from batch timing noise.
Grid40 remains dominated by partition materialization/architectural evaluation;
its one-digit-ms target is not met. No candidate pruning or weakened validity
proof was used to obtain the measured values.

Reproduce the coverage audit with the fixed corpus:

```bash
python python/audit_roof_support.py --corpus python/docs/canonical/support_grid.json.gz --output python/out/support/audit.json --details python/out/support/assignments.jsonl
python python/benchmark_generation.py --samples 9 --warmup 2 --buildings 1000 --output python/out/support/benchmark.json
python -m unittest discover -s python/tests
```

The audit stores source revision/dirty flag, decompressed corpus digest, incomplete
search reason, every failed assignment and every local relation issue. Details
are streamed; only aggregate summaries need to remain in memory.

## Remaining scope

- Offset/width-step continuation, partial-end and parallel need complete indexed
  port/junction operations. Laycock's compatible-collinear merge and Hu's end-cap
  restrictions do not specify arbitrary step/offset incidence; importing an
  assumed ridge continuation would incorrectly claim support.
- Mixed terminal/middle networks, multiple receivers, repeated replacements on
  one end and interacting junction regions remain unsupported. The operation
  does not recursively graft an arbitrary adjacency tree.
- Nonlinear compound geometry solve, convergence/planarity validation and final
  pitched compound Blender mesh output remain unimplemented. Independent planar
  witnesses prove the new graph incidences admit the tested embeddings; they are
  not a shipped mesh solver. Multi-cell hip/shed and Geometry Nodes generation
  remain separate work.

The measured top three relation gaps take priority in further research. Published
parallel avoidance is a partition ranking rule, not a missing junction template.
This series therefore implements the justified distinct-end extension and leaves
those incomplete operations explicit instead of inventing fixture-specific rules.

Verification: 106 unit tests pass, including fixed topology witnesses, eave-derived
receiver height anchors, independent planar coverage, metamorphic seed checks,
minimum partition proofs and unknown-grid partition tests. Blender 4.3.2
installed-ZIP smoke passes. Its real mesh cases remain rectangle types and
concave flat surfaces; it checks explicit/atomic compound-solve failure rather
than pretending the U Graph is a finished Blender pitched mesh. Package source
matching passes. The runtime remains standard-library-only.
