# Published branch composition evaluation

Starting SHA: `ac1ff8b6b8387aab92e91801d12c9eafad3ed19c`.
Clean measured implementation: `4797dfc8b62f9602c93e05fb768982bca647cf41`.
Inspection source: `a666cd7` (later changes only add secondary proof/evidence).
The final SHA is given by the task report and Git history.

## Result and stop boundary

`compose(cells)` now consumes a researched **terminal attachment**, a
**middle side attachment**, or **disjoint narrower middle attachments on one
host** into one RoofGraph. The branch's internal gable cap is removed; a narrow
middle branch terminates on the receiving slope with two valleys while the
main ridge remains continuous. At equal widths it joins the host ridge, with
three ridge segments and two valleys at one five-valent junction.

This is a bounded graph-first composition evaluation, not a general roof
generator or integrated multi-cell geometry solve. U, cross templates,
interacting/multiple terminal attachments, same-axis continuation, architectural
aggregation from arbitrary minimum cells, multi-cell hip/shed/flat and oblique
parts remain unimplemented. Unsupported arrangements return no composed graph.
The original addon/production route, partition algorithm and frozen harnesses
are unchanged. The four single-rectangle primitives still pass their mesh proof.

## Research decisions carried into code

The first commit, `d8abb01`, only added
[ROOF_COMPOSITION_RESEARCH.md](ROOF_COMPOSITION_RESEARCH.md). It contains the
required source and case matrices, A/B/C/D adoption classification, original
access/section details and prior decision reassessment before algorithm edits.

| Reread source | Actual post-partition operation | This implementation / limitation |
| --- | --- | --- |
| Laycock & Day 2003, Section 7, Figures 4–6 | Aggregate elementary rectangles into larger boundaries before roofing; merge side branches (case 1) and models with two collinear exterior edges (case 2). Skeleton-derived aggregation is part of their method. | Consume a complete end port against a partial eave side and splice the branch slope cycles. Do not transplant the forbidden skeleton backend. Same-axis continuation and arbitrary aggregation are only mapped, not implemented. |
| Sugihara & Hayashi 2006, Sections 3–4 | Fat-rectangle partition and CG/CSG construction/placement. It does not give the later narrow/wide junction algorithm. | Correct the prior combined attribution. Keep the already proved minimum partition; do not restore their different greedy decomposition. |
| Sugihara & Hayashi 2007, pp. 312–313, Figures 5–6 | With common slopes, a narrow/lower branch extends into a wider/higher main; DL length supplies branch width. Multiple branches are illustrated. | Width relation selects narrow middle termination topology; internal cap disappears, main ridge survives, two reflex-to-junction edges are valleys. The indexed cycle splice is explicitly our adaptation of the extension, not claimed as printed pseudocode. |
| Sugihara & Kikata 2013, pp. 479–480 | Explicitly extends the partitioned rectangle to the wider main and warns fat rectangles alone did not always produce plausible roofs. | Additional investigation supports the above mapping but does not resolve arbitrary minimum-cell aggregation or interacting extensions. No CSG or inner-contour skeleton is used. |
| Kada & McKinley 2009, Sections 2.2–2.4, Figure 11 | Fit primitive roofs from LiDAR; reexamine cells with consecutive-side/three-side neighbors and replace by compatible corner/T/cross junction blocks joining the most neighbors. | Withdraw blanket rejection of junction incidence. Equal-width middle uses T port incidence. Recognize the complete adjacency arrangement before editing. Cross block recovery and the original neighbor-fit selection are not claimed without their missing architectural/fitted parameters. |
| Ren et al. 2021, Sections 3–4 | Primal cycles/dual adjacency encode selected topology, then optimize its planar embedding. | Existing RoofGraph/GeometryProblem contract is used. The solve cannot change roles, face cycles or edge meanings. No nonlinear solver is added. |

The previous design rejected Kada junction classes alongside LiDAR/outline
generalization, and selected only supporting-plane/reflex/aspect ideas from the
other sources before plane-envelope composition. The repository records those
choices and their wider/oblique scope; it does not prove junction incidence
itself was unsuitable. This series withdraws that blanket decision while keeping
the specified backend/input restrictions. No undocumented historical motive is
asserted.

## Data flow and decision ownership

1. `analyze(points)` and the unchanged classical `decompose` return
   Cell/Side/Adjacency/exterior spans. No roof parameter enters partitioning.
2. `cell_primitives` supplies candidate incidence and explicit gable ports;
   their existing orientation policy is retained. These graphs are diagnostic
   candidates, never an output substitute for a failed composition.
3. `connections.attachments` groups noded shared intervals by incident sides.
   It recognizes a complete branch gable end against a partial host eave side,
   checks the other branch sides are exterior, and distinguishes terminal/middle
   by contact with one/no host-side corners. Primitive ports must be compatible.
4. `connections.plan` checks the **whole** arrangement. A terminal operation is
   currently isolated. Middle operations must identify one host and distinct
   exterior leaf branches covering all cells. No area/centrality score chooses
   a main cell. A narrow branch must have less transverse width than its host;
   the single equal-width case is a separate T incidence. Square/fat default
   orientations that do not match fail rather than silently rotate.
5. `topology._terminal` retains the existing proved corner graft. Both near
   ports disappear, and the convex/reflex spokes are hip/valley. The unequal
   case has two trivalent junctions and an intervening hip, preserving the
   wider roof. `host` here means receiving geometric side; it need not be the
   higher architectural roof when the attached primitive is wider.
6. `topology._middle` rewrites cycles. Narrow: host eave interval becomes
   `reflex -> J -> reflex`, and branch near port becomes J. Host ridge/opposite
   slope remain. Equal: also node the host ridge at J and split the attached
   host slope into two connected cycles, avoiding a self-touching face.
7. Multiple narrow slots must be strictly separated when projected along the
   common host ridge direction, even on opposite sides. Sort the whole slot
   set along each host side and build each host slope once. Edits affect
   disjoint paths/vertices, so adjacency order cannot choose a different graph.
   No sequential pairwise merge, overlay or roof plane is used.
8. Only after meanings/cycles are fixed, `geometry.middle_seeds` assigns a
   disposable drawing. Narrow J starts inside the host slope strip; equal J
   lies on the declared host ridge axis. The midpoint used for narrow initial
   XY is an explicit initializer, not the reason to create J or a final roof
   geometry solve. Independent metric witnesses differ from these seeds.
9. `problem(graph)` exports the fixed cycles, variable XY/Z, fixed boundary,
   nonzero cap-height anchors and ridge directions. No topology decision is
   delegated to SGA21; no nonlinear solve or final multi-cell mesh is reported.

`Composition.connections` contains host/branch IDs, consumed primitive ports,
shared interval, chosen junction IDs, wider primitive and operation kind.
Inspection schema 2 replaces the prototype's singular connection field.
Face and vertex cell provenance follow originating primitive faces; exterior
provenance follows source boundary spans, not visible-solid reconstruction.

## Concrete graph results

| Input | Cells | V/E/F | Retained ridge segments | Valleys | Hips | Internal degrees |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| [Existing L](composition/orthogonal_L.svg) | 2 | 10 / 13 / 4 | 2 | 1 | 2 | 3, 3 |
| [Existing T / narrow middle](composition/orthogonal_T.svg) | 2 | 12 / 15 / 4 | 2 | 2 | 0 | 3 |
| [Equal middle](composition/middle_equal.svg) | 2 | 12 / 16 / 5 | 3 | 2 | 0 | 5 |
| [Off-center middle](composition/middle_offset.svg) | 2 | 12 / 15 / 4 | 2 | 2 | 0 | 3 |
| [Two separated branches](composition/multiple_disjoint_middle.svg) | 3 | 18 / 23 / 6 | 3 | 4 | 0 | 3, 3 |
| [Unknown grid branches, 20 corners](composition/grid_branches_20.svg) | 5 | 30 / 39 / 10 | 5 | 8 | 0 | four 3s |
| [Unknown grid branches, 40 corners](composition/grid_branches_40.svg) | 10 | 60 / 79 / 20 | 10 | 18 | 0 | nine 3s |

The last two are unselected-shape inputs from the supported domain generator,
seed 4107 (first examples of each vertex count), not replacements for the
existing unrestricted-grid fixtures. Although real branches may have parallel
ridges, all connect into the same main roof; their independent internal gable
ends/artificial rectangle cuts are absent. One unsplit main ridge persists.

[Overview](composition/overview.png) was generated from actual inspection JSON
and visually checked. Each SVG separates cells/cuts/adjacency, primitive ridge
candidates and final retained features. Matching JSONs expose every cycle,
source span, candidate relation, applied operation and geometry problem.
No imported paper drawing is used.

## Explicit unresolved cases

| Existing input | Minimum cells | Result / reason |
| --- | ---: | --- |
| [U](composition/orthogonal_U.svg) | 3 | Its cells do not yield the complete supported middle arrangement; multiple interacting terminal/receiver roles need a new mapped operation. |
| [Cross](composition/cross.svg) | 3 | Opposite equal-width branches require a single shared cross template; two independent T operations would coincide. Kada provides a candidate template, but it has not been transferred/proved here. |
| [Residential](composition/residential_multi_reflex.svg) | 4 | Local candidates do not form the supported one-host/leaf arrangement; architectural aggregation or more junction operations are needed. |
| [Original grid 14](composition/grid_14.svg) | 5 | No complete supported port arrangement. |
| [Original grid 20](composition/grid_20.svg) | 7 | No complete supported port arrangement; inspect the individual candidate ridges, not a pretend merged roof. |
| [Original grid 40](composition/grid_40.svg) | 12 | Same limitation with multiple regions requiring aggregate/junction recognition. |

Other explicit failures cover a square receiver whose chosen primitive axis
does not match, overlapping projected narrow slots, middle branches wider than
their receiver, and unimplemented multi-cell hip/shed/flat requests. Some can
have valid roofs; failure means they lack a supported/proved composition rule,
not that no building roof exists.

The papers do contain aggregation and junction mechanisms. What remains missing
is their direct, deterministic application to this **fixed minimum partition**
without skeleton, CSG or fitted LiDAR parameters, especially when several cells
must first become a different architectural part. Additional investigation of
Sugihara & Kikata and Ren does not resolve that mapping. No invented global
main/branch heuristic or general mathematical envelope fills the gap here.

## Proof and regression

All **76** tests pass. New primary proofs include:

- Independent literal cycles and nonflat planar XYZ witnesses for narrow,
  equal, offset and multiple middle cases. These are test evidence, not values
  production reads. Compare exact oriented cycles, feature meanings, exterior
  and Cell ownership, consumed caps/cuts and junction incidence.
- Fixed-boundary graph disk, connected faces, oriented two-face internal edges,
  manifold vertex links and one exterior cycle remain constructor obligations.
  Independent polygon unions check noncrossing seed coverage/no overlaps.
- Translation/rotation, cyclic/winding/collinear variants and reversed adjacency.
- **100 unknown connected-grid buildings**, seed 4107, in the explicit
  longitudinal-main/separated-narrow-branch domain: main ridge continuity,
  2 valleys per branch, no hips, trivalent terminations, two source slope faces
  per primitive, exact coverage and independent common-pitch metric witnesses.
  The unrestricted 500-shape minimum partition proofs also remain unchanged.
- Fault injection replacing a valley or main ridge by hip fails the independent
  semantic/cycle oracle. Interacting/equal-width cross and unsupported roles
  fail without producing a graph.
- Fresh isolated process blocks NumPy/Shapely/reference-generator imports while
  all four new connection reference fixtures compose successfully.
- The existing frozen T snapshot matches the new graph's cycles and every edge
  meaning; original L differential/witness proofs still pass. Visible-solid
  part contributors are not forced onto primitive-origin Cell provenance.

The unchanged semantic CLI matches all **27** snapshots. The distribution ZIP
matches source. Local Blender 4.3.2 rectangle mesh/UV/material smoke passes;
no multi-cell final Blender mesh is asserted. CI retains Windows/Linux,
Python 3.11/3.13 and installed/source Blender checks.

## Unprofiled stage performance

[Recorded measurement](composition/performance.json), clean SHA above,
Python 3.12.14/Linux x86-64, 101 samples after 5 warmups, cache none. The new
driver reuses the **unchanged `benchmark_graph_first.measure`**. Graph time
includes primitive incidence, complete relation recognition, cycle rewrite,
drawing and full Graph/XY guards. Input creation is outside the timed calls.
Stage medians need not sum to the directly measured total median.

| Case | Analysis ms | Partition ms | Graph ms | Footprint→Graph ms | Total p95 ms | Geometry-problem ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| L | 0.087 | 0.413 | 1.157 | 1.745 | 2.443 | 0.019 |
| T narrow | 0.127 | 0.460 | 1.253 | 1.966 | 2.561 | 0.021 |
| Equal middle | 0.119 | 0.537 | 1.551 | 2.362 | 5.197 | 0.022 |
| Two branches | 0.197 | 0.827 | 2.248 | 3.439 | 4.693 | 0.025 |
| Grid branches 20 | 0.481 | 1.737 | 4.308 | 6.618 | 10.676 | 0.032 |
| Grid branches 40 | 1.438 | 5.121 | 11.932 | 18.574 | 24.204 | 0.048 |

**1000 distinct supported buildings** take **9.231 s**, including analysis,
partition, composition, geometry-problem export and measurement overhead.
Footprint→Graph per-request median/p95: **8.171 / 18.226 ms**. No nonlinear
solve or mesh conversion is included. Thus the 40-corner domain is interactive
at this scope but does not meet a stronger single-digit-ms total target, and
the batch result is not real-time city mesh throughput. The quadratic drawing
guards and graph work remain measurable cost; this task does not conceal that
by timing cached graphs or failing requests as successes.

```bash
python python/benchmark_roof_composition.py --samples 101 --warmup 5 --buildings 1000
python python/inspect_roof_composition.py --fixture orthogonal_T
python python/inspect_roof_composition.py --fixture cross  # writes unsupported inspection; exits 2
```

Runtime remains standard-library only. Shapely appears only in independent
proof/reference paths; no overlay, plane envelope, solid Boolean or wavefront
enters the new composer. There is no separate mesh semantic authority.

The evaluation boundary is reached: researched terminal/middle graph operations
and a justified simultaneous noninteracting multiple subset. Further cross,
terminal interaction, architectural aggregation, hip/shed/flat and geometry
solving require separate decisions/proofs; none require changing the existing
roof-independent minimum rectangular partition contract.
