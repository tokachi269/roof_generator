# Generic minimum rectangular partition evaluation

## Result and scope

`graph_first.cells.decompose(analyze(points))` now partitions arbitrary-reflex,
hole-free simple orthogonal polygons into minimum-count rectangles. It has no
roof parameters or dependency on roof generation. The single-reflex two-candidate
selector, aspect/cut cost and legacy assembly have been removed, without an
L-specific fast path. There is no recursive search, raster backend, wavefront,
Boolean, polygon library or completed-roof candidate.

Starting SHA: `9bec1849254ee12c303378a85966c769d4f3b7a0`.
Clean measured implementation SHA: `e95bdb88996ac65b0716322f66b3c8f975c234d1` (also recorded in the
[performance JSON](partition/performance.json)). Later commits add an explicit
Steiner proof and evaluation evidence only; the task report gives the final SHA.

The addon, distribution ZIP, production generator, original acceptance tests,
semantic/performance harnesses and frozen semantic fixtures are unchanged.
`topology.py` and `geometry.py` are also unchanged in this series: four rectangle
primitives and the existing terminal-graft proof remain. This work does not add
T/U roof rules, multi-cell hip/shed roofs or a nonlinear solver.

## Source-to-implementation mapping

The [design note](MINIMUM_RECTANGULAR_PARTITION.md) records source access, exact
scope, degeneracies and the guarantee before implementation. The main readable
basis is [Eppstein Section 3, PDF pp. 3–5](https://arxiv.org/pdf/0908.3916),
which attributes the result to Lipski et al. (1979), Ohtsuki (1982), and Ferrari,
Sankar & Sklansky (1984). The accessible [Liou, Tan & Lee 1990 paper, Section II,
pp. 720–721](https://ir.lib.nycu.edu.tw/server/api/core/bitstreams/fa99356d-1701-4965-ae44-4199238328c8/content)
explicitly gives the six classical steps and completion principle. Its 1989
conference version is referenced in the note; the specialized faster algorithm
is not reproduced. Unavailable original full texts are not claimed as read.

| Classical step | Implementation / retained evidence |
| --- | --- |
| Extract reflex corners | `footprint.analyze`: scalar simple-polygon validation, collinear normalization, original edge groups and intrinsic frame |
| Enumerate good diagonals | `rectangle_partition.good_diagonals`: first visible inward boundary hit at another reflex; closed endpoints, strictly interior open segment |
| Build H/V intersection graph | `intersection_graph`: closed-segment conflicts, including shared endpoints; same-axis conflict rejected |
| Maximum matching | `maximum_matching`: deterministic iterative Hopcroft–Karp, actual matched diagonal ID pairs retained |
| Maximum independent set | `independent_set`: unmatched-H alternating reachability, complement of König minimum vertex cover |
| Complete remaining reflexes | `complete_cuts`: intrinsic vertical incident-edge extension to nearest boundary or established partition segment |
| Extract planar subdivision | `subdivide`: shared endpoint noding, directed half-edge cycles, rectangular faces, Euler/count/reflex/area guards |
| Cells, shared intervals, provenance | `cells.from_subdivision`: four geometric corners plus noded boundary, exterior spans and artificial atomic intervals, incident side IDs |

`Decomposition.certificate` holds reflex IDs, every diagonal with endpoint IDs
and intrinsic axis, every conflict, maximum matching, selected independent-set
IDs, completion endpoints/source IDs, and the expected minimum. It replaces the
prototype's candidate-count field. Diagonal endpoints reference the original
normalized vertices, which remain the prefix of the subdivision's vertex list.

### Minimum-count argument

For n normalized corners and r reflex corners, the simple orthogonal identity is
`n=2r+4`. Let D be the good diagonals, M a maximum matching and G the selected
maximum disjoint set. The certificate uses

`|G| = |D| - |M|`, `R_min = r - |G| + 1`.

Open-interior validity forbids a diagonal from passing through another boundary
vertex or overlapping a boundary edge. At a reflex there is one inward ray per
axis, so same-direction diagonals cannot overlap/share endpoints. All conflicts
are H/V, including endpoint conflicts. Selected diagonals have distinct endpoints
and resolve 2|G| reflexes. Each remaining extension stops at its first existing
side, splits one region and resolves one corner. Connecting two still-unresolved
corners through free interior would add another disjoint good diagonal and
contradict maximality of G. Thus the construction attains the classical lower
bound with `1+|G|+(r-2|G|)` rectangular faces. The runtime requires that exact count.
This guarantee uses the hole-free simple orthogonal input and resolved-feature
numerical tolerance; it is not a statement about hole/curve/nonorthogonal input.

### Deterministic implementation choices

There is no new partition optimization problem. Ordered traversal gives repeatable
matching; König recovery supplies one maximum independent set. Vertical
completion is one of the choices expressly permitted by the classical method,
with no aspect, cut-length or roof-quality weighting. Cell/node ordering is
geometric in the existing intrinsic frame.

First-hit ray enumeration is equivalent to testing every aligned reflex pair:
a farther boundary contact invalidates the open segment. A boundary segment
parallel to the ray still has a perpendicular incident edge at its endpoint, so
its first contact is included. The initial implementation redundantly rechecked
candidate visibility; measurements identified that duplication and it was removed.
Conservative bounding-box exclusion before the existing intersection predicate
also reduces work; the design note proves its 2*EPS allowance preserves the
narrow predicate. Neither change selects a different cut or weakens minimum count.

For genuinely quarter-turn symmetric outlines, such as a regular cross, selecting
one asymmetric minimum cannot be exactly rotation-equivariant without an external
axis: the same input would have to return two differently oriented answers.
Tests require equal minimum count, valid ownership and partition equivalence under
**actual outline rotational automorphisms** there. Asymmetric inputs require the
same physical cuts after undoing transforms. Repeated identical input returns an
identical full record. This is an explicit symmetry qualification, not a claim
that physical cut orientation is uniquely determined for all symmetric buildings.

## Concrete results and inspectable certificates

[Partition overview](partition/partitions.png) was generated from actual inspection
JSON and visually checked. Each [inspection CLI](../inspect_rectangle_partition.py)
can also take an arbitrary ordered XY polygon; fixture names are tool inputs only
and never reach the algorithm.

| Case | n | r | Good diagonals D | Matching M | Selected IDs / count | Completions | Minimum cells |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| Rectangle | 4 | 0 | 0 | 0 | none / 0 | 0 | 1 |
| L | 6 | 1 | 0 | 0 | none / 0 | 1 | 2 |
| T | 8 | 2 | 1 | 0 | `[0]` / 1 | 0 | 2 |
| U | 8 | 2 | 0 | 0 | none / 0 | 2 | 3 |
| Cross | 12 | 4 | 4 | 2 | `[2,3]` / 2 | 0 | 3 |
| Residential multi-reflex | 12 | 4 | 1 | 0 | `[0]` / 1 | 2 | 4 |
| Staircase | 14 | 5 | 0 | 0 | none / 0 | 5 | 6 |
| Comb | 20 | 8 | 4 | 0 | `[0..3]` / 4 | 0 | 5 |
| Zig-zag | 10 | 3 | 0 | 0 | none / 0 | 3 | 4 |
| Multiple indentations | 12 | 4 | 0 | 0 | none / 0 | 4 | 5 |
| Comb 40 | 40 | 18 | 9 | 0 | `[0..8]` / 9 | 0 | 10 |
| Generated grid 14 | 14 | 5 | 2 | 1 | `[1]` / 1 | 3 | 5 |
| Generated grid 20 | 20 | 8 | 3 | 1 | `[1,2]` / 2 | 4 | 7 |
| Generated grid 40 | 40 | 18 | 13 | 6 | `[6..12]` / 7 | 4 | 12 |
| Interior Steiner example | 10 | 3 | 1 | 0 | `[0]` / 1 | 1 | 3 |

Full diagonals, matching pairs and selected coordinates are in the
[T](partition/orthogonal_T.json), [U](partition/orthogonal_U.json),
[residential](partition/residential_multi_reflex.json), [cross](partition/cross.json),
[comb 40](partition/comb_40.json), [grid 14](partition/grid_14.json),
[grid 20](partition/grid_20.json), [grid 40](partition/grid_40.json) and
[Steiner](partition/interior_steiner.json) outputs, with companion SVGs.
Cross conflicts all occur at original shared endpoints; testing only proper
crossings would yield the wrong minimum. Boundary reflex edges are not good
diagonals and long same-coordinate chords cannot pass through other boundary
contacts. Boundary Steiner hits split provenance into contiguous intervals.

The Steiner example has a completion ending at world `(3,1)` inside a good
diagonal. That one vertex belongs to all three cell boundaries, is collinear
on one rectangle side, and has three shared intervals. Its cell dual is a
three-cycle. Adjacency is not forced to be a tree, and a geometric rectangle's
four corners are deliberately distinct from its fully noded boundary. This
prevents downstream unshared T endpoints without subdividing a rectangle into
extra cells and losing optimality.

### Existing graph-first L integration

The [L partition](partition/orthogonal_L.json) still gives the same two physical
rectangles: `[5.2,14.2] × [0,5.6]` and `[0,5.2] × [0,12.8]`, with shared
interval `(5.2,0) → (5.2,5.6)` and all six exterior source edges. Passing those
Cells directly to the unchanged terminal graft gives 4 roof faces, 2 ridges,
2 hips and 1 valley, with two three-valent internal junctions. All original
connection, semantic differential and independent embedding-witness proofs pass.
This confirms the partition contract, not a newly implemented L nonlinear solve.

## Primary verification

`test_rectangle_partition.py` and `test_partition_grid.py` provide separate proof
from existing roof harnesses:

- Literal minimum counts for rectangle/L/T/U/cross/staircase/comb/zig-zag/
  multiple-indentations/residential/20–40-corner and Steiner polygons.
- Independent raw-vertex reflex detection and GEOS all-pairs/open-interior
  diagonal visibility. An exhaustive bitset independent-set oracle computes
  theoretical optimum without invoking production matching/partition helpers.
- All 512 possible 3×3 bipartite graphs are compared with exhaustive independent
  sets, catching incomplete augmenting paths/cardinality errors.
- 500 unknown connected-grid shapes, seed 92821: 8–40 normalized corners,
  minimum cell counts 2–15, diagonal counts 0–14, matching sizes 0–7.
  [Distribution/proof summary](partition/generated-proof.json). There are 21
  14-corner, 37 20-corner and 39 40-corner shapes in this primary set.
- Every generated output is checked for four right-angle corners, positive
  simple rectangles, disjoint interiors, exact union, opposite directed internal
  incidence, two-cell artificial interval ownership, exact shared-boundary
  adjacency, exterior interval coverage/provenance, no dangling cuts, resolved
  reflex corners and Euler disk. Tests inject missing adjacency and removed
  provenance and require failures.
- Translation/rotation, cyclic start, winding and redundant collinear points
  are tested on named cases and 20 additional unknown shapes. Physical cuts
  agree on asymmetric shapes; the stated symmetry qualification applies only
  to true outline automorphisms.
- A fresh isolated interpreter forbids Shapely, NumPy, roof composition, geometry
  solver and production-generator imports while partitioning every fixture.
  Nonorthogonal, hole-shaped/nested, self-intersecting and touching inputs fail.

All **64** core tests pass, including all original production/roof proofs.
The unchanged semantic CLI still agrees on all **27** frozen snapshots. The addon
ZIP still matches canonical source. Blender 4.3.2 also passes the unchanged
independent rectangle mesh/UV/material smoke after this partition replacement.
Existing CI runs these proofs on Windows/Linux, Python 3.11/3.13, together with
installed-addon and source Blender smoke; no existing gate is weakened.

## Unprofiled performance

[Measurement JSON](partition/performance.json) records clean source SHA, Python
3.12.14, Linux x86-64, 101 samples after 5 warmups, no profiler and no cache.
The final run preceded other compute-heavy checks. Input generation is explicitly
excluded; analysis and all partition guards/records are included. The raw output
can be reproduced with:

```bash
python python/benchmark_rectangle_partition.py --samples 101 --warmup 5 --buildings 1000
```

Median milliseconds below. Whole-call totals are measured directly; they need
not equal the sum of independent stage medians.

| Case | Analysis | Diagonals | Conflict graph | Matching | MIS | Completion | Subdivision | Cell records | Total | Total p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Staircase 14 | 0.190 | 0.175 | 0.002 | 0.003 | 0.004 | 0.158 | 0.393 | 0.213 | 1.167 | 1.563 |
| Grid 14 | 0.190 | 0.187 | 0.009 | 0.008 | 0.005 | 0.097 | 0.340 | 0.178 | 1.031 | 1.424 |
| Comb 20 | 0.331 | 0.421 | 0.015 | 0.007 | 0.006 | 0.005 | 0.470 | 0.205 | 1.516 | 2.010 |
| Grid 20 | 0.333 | 0.417 | 0.016 | 0.010 | 0.006 | 0.179 | 0.595 | 0.268 | 1.874 | 2.476 |
| Comb 40 | 1.133 | 1.751 | 0.060 | 0.011 | 0.009 | 0.008 | 1.405 | 0.418 | 4.930 | 5.747 |
| Grid 40 | 1.091 | 1.788 | 0.201 | 0.030 | 0.011 | 0.338 | 1.590 | 0.485 | 5.661 | 6.997 |

L/T/U totals are 0.299 / 0.389 / 0.473 ms; residential is 0.856 ms. The first
clean measurement at `ea76add` had 8.944 / 10.948 ms for comb/grid 40. Removing
duplicate visibility and adding conservative box exclusion reduced that work
without changing the algorithm or quality contract; no sophisticated theoretical
range-search data structure was needed.

A batch of **1000 distinct geometries**, seed 92821, 6–40 corners, produces
**7982 cells in 3.000 s**, including input analysis and full partition records.
Per-building median is 2.933 ms and p95 is 5.515 ms. No geometry memoization or
same-input repetition is used. These are partition timings, not city roof-mesh,
Blender-object or nonlinear-solver throughput claims.

## Dependencies and next boundary

Partition runtime uses **only the Python standard library**. Shapely appears
solely in independent tests and the unchanged reference production route;
NumPy is test-only here. `BoundarySpan` and `UnsupportedGraphError` reuse the
existing contract types, without invoking RoofGraph logic. The development
benchmark's grid generator only creates inputs before the timed core and is
not imported by production modules. No dependency or distribution change occurs.

The partition can be reused unchanged for all-gable, all-hip, shed, flat or
mixed primitive assignments: no type, pitch, eave or plane was consulted to
select it. The next owner must compose primitive graphs using noded cell
boundaries, side intervals and arbitrary adjacency (including cycles). That
requires new topology operations/proofs, not a gable-specific repartition or
changes to this geometry-only minimum contract. Architectural direction or
secondary roof-quality selection among equal minima would be explicit separate
requirements, not reasons to weaken minimum count here.

This task stops at generic Cell graph and preserved L integration. Holes,
curves and nonorthogonal decomposition remain unsupported; the nonlinear solver
and generic multi-cell roof composition are next tasks.
