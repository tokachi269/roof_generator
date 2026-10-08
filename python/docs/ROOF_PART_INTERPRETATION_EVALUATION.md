# Architectural part interpretation evaluation

Start: `7d33cb84dc6c3ed32af2cf154770db3df6981128`.
Measured implementation: `f46ff7149f8bc21bb57b1805de279696e5be78f5`, clean source.
The final evidence commit adds this report, README usage and the recorded
artifacts; it does not change that measured implementation.

The new path produces inspectable architectural interpretations for the original
U, Cross, residential and generated-grid inputs. It preserves unresolved roles
and directions. It does **not** produce a compound RoofGraph or final mesh.
Existing production generation, graph composer, solver and addon are unchanged.

## Sources and processing order

The full [research note](ROOF_PART_INTERPRETATION_RESEARCH.md) was committed
before production changes. Its source table covers elementary cells, alternative
partitions, aggregation, roles, roof units and junction timing.

| Source and location | Processing actually used here | Boundary of adoption |
| --- | --- | --- |
| Laycock & Day 2003, Section 7, Fig. 4–6 | Explicit cell membership followed by grouped exterior-boundary extraction. Shared oriented atomic edges cancel; surviving edges form cycles. | Their skeleton-grown region discovery is not copied or replaced by a new skeleton. Hu's combinations provide the limited grouping interpretation used here. |
| Hu, Fan & Noskov 2017, Sections 3.1–3.5, Fig. 3–19; threshold in Section 5.2 | Matching-based maximum independent sets, horizontal/vertical completion alternatives, published fragment/parallel/symmetry terms, one-line and corner compound units, full-short-end/partial-long-side attachment constraints. | Canonical completion order is explicit. Exact reflected region components replace approximate extended-centerline matching conservatively. End-triangle options, probability models and final roof recommendations are not implemented. |
| Kada & McKinley 2009, Sections 2.1–2.4, Fig. 8–11 | Preserve the distinction between basic parts and later neighbor-dependent junction replacement. | Their fitted LiDAR roof types/parameters are unavailable here. No fabricated fit, junction replacement or cross roof is produced at this stage. |
| Sugihara & Hayashi 2007, Section 4(2), pp. 312–313; Sugihara & Kikata 2013, pp. 479–480, Fig. 3 | Local transverse-width comparison explains the narrower-branch/wider-receiver hypothesis under common pitch. | Their extraction order and greedy partition are not restored. No global largest-area main, extension geometry or Boolean is introduced. |
| Sugihara & Hayashi 2006, Sections 3–4 | Distinguish extracted building parts from later construction. | The later narrow/wide extension is not attributed to the earlier fat-rectangle/CSG paper. |

The prior Cell-to-primitive composer lacked alternative partition selection and
compound architectural units. This series changes that responsibility boundary
rather than adding U/Cross/Grid-specific junction rules. The research does not
justify a complete arbitrary-footprint roof grammar; the missing cases below
remain explicit.

## Data flow and contracts

```text
ordered footprint
  -> intrinsic orthogonal analysis
  -> certified minimum partition candidate family
  -> member axis domains and all adjacency combination options
  -> published evaluation terms with unresolved score bounds
  -> retained ArchitecturalPartGraphs
  -> inspection only (future topology composition is a separate task)
```

`Cell` is a rectangle in an exact minimum geometric partition. It has no roof
meaning. `ArchitecturalPartGraph` contains:

- `Member`: source Cell, exact rectangle bounds and possible long axes.
- `Relation` / `Combination`: source Cell/Side pair, shared intervals, axis
  assignments, continuation/corner/side-attachment/parallel/partial-end options,
  receiver/branch and transverse widths. `main` exists only for a strictly wider
  local receiver; equal width does not imply a main.
- `Part`: member Cells, exact exterior cycles, exterior source spans, consumed
  artificial cuts and member axis domains.
- `PartAdjacency`: remaining inter-unit shared intervals and source Cells.
- `Issue`: inspectable square-axis, width-role, unresolved-contact or compound
  boundary limitation.

All relations are recognized before grouping. Connected components of
unambiguous corner/continuation relations form compound units simultaneously.
Strict middle attachments remain between units. Grouping never removes local
constraints, including unresolved contacts between members of one compound.
This is not sequential pairwise roof merging. Every Cell belongs to exactly one
unit in each interpretation, all exterior provenance survives, consumed cuts
are recorded and grouped coverage remains exact.

Minimum Cells cannot be merged into a larger exact rectangle: doing so would
contradict the certified minimum count. A compound unit can therefore be concave
and retain several rectangular members. It is not one independent gable or
one parametric hip. Artificial cuts have no ridge/valley/hip/eave meaning.

## Alternative minimum partitions and selection

The existing good diagonals, bipartite conflicts, maximum matching and
`r - |MIS| + 1` minimum certificate remain authoritative. Every returned
candidate is validated against the certificate and rectangular subdivision
contract. The original scalar partition is preserved.

For a matching of size M in a graph with N vertices, any maximum independent
set of size N-M contains every unmatched vertex and exactly one endpoint of
each matching edge. The implementation enumerates those choices, rejecting
conflicts early. This is exact index-based pruning. Both axes are then tried
for unresolved reflex vertices in canonical order. Identical cuts/subdivisions
are deduplicated, and actual footprint symmetries add certified image cuts.

The search is complete **within that stated family**, not every possible
Steiner completion order. Default limits are 4,096 candidates and 65,536 work
visits. Hu supplies no polynomial candidate bound or guaranteed safe top-k
ranking. A reached limit reports `incomplete`, keeps inspectable partial results
and recommends no winner. No truncated pool is called optimal. The six original
cases complete within those limits, with at most 48 subdivisions/116 visits.

Evaluation uses Hu's literal terms: -1 per fragment, -2 per parallel pair and +1
per connected symmetric pair of subclusters. The 3-metre threshold and input
unit conversion are explicit. Fragments remain members instead of being omitted
as in the paper's later roof processing. Exact reflected connected rectangle
halves implement the four connectivity/reflection conditions conservatively;
approximate outline generalization and all extended-centerline cases are not
claimed. Independent reflection witnesses are tested.

Square axes can change parallel penalties. Scores remain safe lower/upper
bounds over their assignments. A candidate survives when its upper bound is
at least the best lower bound. Thus retained candidates may still need an axis
choice; the system does not claim all retained scores are equal or uniquely
optimal roofs. Candidate symmetry orbits preserve equivalent directions.

These adaptations have explicit purposes: exact source geometry and coverage,
bounded resource use without false winners, and preservation of unresolved
architectural choices. No additional weighted aesthetic score is used.

## Original cases and inspection results

All six inputs are the existing fixtures, including the original grid14/20/40
records. None is replaced by an easier generated shape. Counts below refer to
the complete evaluated family. Unit/cut ranges are over retained candidates.

| Input | Minimum Cells | MIS choices | Candidates | Work visits | Retained | Architectural units | Consumed cuts | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| U | 3 | 1 | 4 | 10 | 2 | 1 | 2 | ambiguous |
| Cross | 3 | 2 | 2 | 22 | 2 | 3 | 0 | ambiguous |
| Residential | 4 | 1 | 4 | 6 | 1 | 2 | 2 | partial |
| Grid 14 | 5 | 2 | 12 | 20 | 10 | 4–5 | 0–1 | ambiguous |
| Grid 20 | 7 | 1 | 16 | 19 | 6 | 2–6 | 1–6 | ambiguous |
| Grid 40 | 12 | 6 | 48 | 116 | 25 | 9–11 | 1–4 | ambiguous |

**U:** candidates 1/2 retain alternate corner ownership. One has a transverse
receiver with two terminal members; the other has two longitudinal receivers
and a connector. Both group all three Cells into one compound boundary, with
two consumed cuts and preserved member constraints. The original transverse
receiver is 5.2 units wide against 5.4-unit arms, so its narrower-receiver issue
is retained. No area ranking silently fixes the role.

**Cross:** vertical and horizontal receiver arrangements occupy the same actual
footprint symmetry orbit `((0, 1),)`. Both remain. Square end members permit
attachment/parallel alternatives and equal widths do not establish a strict
main. The three units are constrained analytic members, not three generated
gable roofs. A shared cross-junction operation is still a downstream task.

**Residential:** candidate 2 retains one member plus a three-member compound
corner unit. Two cuts are consumed; a middle attachment connects the units.
Some local receiving members are narrower, leaving `width_roles`. A unique
retained partition is therefore `partial`, not a ready roof topology.

**Grid 14:** ten candidates survive, with four or five units. The graphs show
which terminal corner cuts can be consumed and which parallel/partial-end or
square-axis choices remain. Some units remain single Cells; that does not assign
them independent gables.

**Grid 20:** six candidates survive. Candidate 14 groups Cells (0,1,2,3,4) and
(5,6), yielding two compound units and six consumed cuts. Unresolved contacts
inside those units still exist. Maximum grouping is shown as an inspection
view; it is not an extra selection score or a proven architectural winner.

**Grid 40:** 25 candidates survive, with nine to eleven units. Candidates 13/43
have nine units and four consumed cuts. Member-axis and interacting-contact
choices remain; grouping neither forces twelve independent gables nor claims
to solve every compound unit's roof.

### Visual and serialized evidence

[Overview PNG](interpretation/overview.png) separates the original minimum
partition, a retained interpretation and an alternative inspection view.
U/Cross show distinct retained directions. Green dotted lines are consumed
cuts, gray dashed lines are retained analytic boundaries and teal arrows are
conditional receiver relations. None is a roof ridge.

| Input | All candidate/grouped diagrams | Full inspection data |
| --- | --- | --- |
| U | [SVG](interpretation/orthogonal_U.svg) | [JSON](interpretation/orthogonal_U.json) |
| Cross | [SVG](interpretation/cross.svg) | [JSON](interpretation/cross.json) |
| Residential | [SVG](interpretation/residential_multi_reflex.svg) | [JSON](interpretation/residential_multi_reflex.json) |
| Grid 14 | [SVG](interpretation/grid_14.svg) | [JSON](interpretation/grid_14.json) |
| Grid 20 | [SVG](interpretation/grid_20.svg) | [JSON](interpretation/grid_20.json) |
| Grid 40 | [SVG](interpretation/grid_40.svg) | [JSON](interpretation/grid_40.json) |

Each SVG includes the full minimum candidate gallery and every retained grouped
graph, rather than just a favorable chosen partition. The JSON retains all
partitions, evaluations, relations, issues and provenance, with source SHA and
clean-source metadata. The figures were visually inspected for boundaries,
distinct alternatives, cut styles and absence of roof-like line semantics.

## Independent proofs and regressions

The final local suite has 101 tests. Added proofs include:

- Exhaustive brute-force MIS comparison for all 512 bipartite 3-by-3 graphs.
- Independent unit-grid rectangle exact-cover enumeration for small L/U/Cross,
  with fixed minimum counts and complete small-case candidate comparisons.
- Independent Shapely coverage/disjointness and grouped exterior comparisons,
  including 30 arbitrary generated-grid footprints across their candidate pools.
  Shapely is an oracle dependency only, not a new runtime dependency.
- Exact membership, provenance, adjacency and consumed-cut contracts;
  fault-injected missing/mismatched data must be rejected.
- Independent axis-assignment score-bound checks and reflected-region witnesses.
- Translation, rotation, cyclic start, winding, redundant collinear vertices and
  adjacency-order metamorphisms for all six original cases.
- Explicit budget/no-winner proof, symmetry-equivalent Cross retention, physical
  unit conversion and fragments retained in coverage.
- Fresh isolated interpreter with forbidden Shapely/NumPy/reference/composer/
  solver imports, proving the new core does not depend on those paths.
- Valid SVG XML and original-fixture inspection counts, with no RoofGraph output.

The existing suite includes the prior 500-generated-shape minimum-partition
proof and semantic harness. No existing test or frozen expectation is weakened.
The distributed addon ZIP still matches source. Existing production topology,
connections, geometry, scalar cells API, footprint analysis, semantic harness,
performance harness, Blender addon and packages have no changes in this series.
New tests for the new path do not claim final multi-cell Blender acceptance.

## Unprofiled stage performance

Python 3.12.14/Linux, 25 measured samples after 3 warmups, no cache or profiler;
input generation is excluded. All candidate analysis/evaluation is included.
[Performance JSON](interpretation/performance.json) records source, policy,
candidate counts, statuses, stage medians and p95. Times are milliseconds.

| Input | Footprint | Candidate generation | Interpretation | Evaluation | Retained graph build | Total median | Total p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| U | 0.109 | 2.674 | 0.112 | 0.168 | 0.192 | 3.465 | 4.032 |
| Cross | 0.201 | 2.323 | 0.069 | 0.122 | 0.262 | 3.150 | 4.683 |
| Residential | 0.179 | 5.127 | 0.152 | 0.291 | 0.155 | 6.079 | 11.618 |
| Grid 14 | 0.222 | 15.786 | 0.714 | 1.486 | 2.475 | 20.962 | 33.607 |
| Grid 20 | 0.377 | 28.624 | 1.298 | 3.066 | 1.912 | 36.285 | 58.032 |
| Grid 40 | 1.379 | 212.156 | 8.164 | 38.147 | 17.765 | 277.707 | 349.829 |

Total medians are measured separately; stage medians need not sum exactly.
These measurements stop at architectural interpretations and include neither
RoofGraph construction, SGA21 solve nor mesh conversion. The earlier 18.57 ms
single-partition Footprint-to-Graph measurement is a different scope.

Forty vertices at roughly 278 ms is not an interactive production replacement.
There is no candidate explosion on this input (48/116), but building/validating
many complete minimum subdivisions dominates. Future performance work must
preserve candidate completeness/ambiguity and inspect those costs before
inventing top-k pruning. This series does not optimize the old plane-envelope
generator or silently trade interpretation quality for speed.

## Evaluation of the next task

The geometric partition and architectural interpretation responsibilities are
now separate. Published terminal/corner/middle relationships can be inspected
on unknown inputs with exact provenance and compound boundaries. This is enough
to define the next **limited** ArchitecturalPart-to-RoofGraph composition task.
It is not evidence that arbitrary retained part graphs have realizable roofs.

Resolve or explicitly retain the following before generic roof composition:

1. Square-member architectural directions and symmetry-equivalent receiver axes.
2. Corner common-section ownership and Hu's shared/T/end-triangle options.
3. Narrower receivers, equal-width roles and conflicts between multiple contacts.
4. Parallel/partial-end attachments and interacting relations inside compound units.
5. Compound concave-unit realization: one unit is not one rectangular primitive.
6. Completion-order coverage if a missing architectural solution lies outside
   the stated candidate family; no current claim of global roof optimality.

No U/Cross/Residential production classifier or fixture-name branch is added.
The structural part contract supports future gable/hip/shed/flat composition,
but Hu's current ranking prior is pitched-roof research. Future flat composition
can consume all artificial cuts; shed needs an explicit architectural direction;
hip must avoid closing each geometric Cell separately. Those tasks should choose
their own declared architectural contracts rather than silently inherit the
pitched-roof ranking or change minimum partition geometry.

Nonlinear solving and Blender multi-cell mesh integration remain separate,
later work. A solver must not decide these architectural roles or roof topology.
