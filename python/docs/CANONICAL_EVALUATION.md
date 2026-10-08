# Canonical roof generation evaluation

Starting SHA: `121533dd6f1152f1bd46d80493b00e7ea84d1783`.
The current pipeline and capabilities are defined in [ARCHITECTURE.md](../../ARCHITECTURE.md).
Measurements and smoke evidence for this series are recorded below.

## Structural results

The distributable core owns the complete candidate-to-GeometryProblem path.
Valid ambiguity is separate from rejected topology and incomplete search. A stable
BLAKE2b namespace selects valid ties, with an explicit physical reference direction
for symmetric input. Square gable seeds 0 and 1 select perpendicular ridge axes;
the symmetric Cross retains two architectural arrangements. The two Cross
arrangements have equivalent physical equal-width four-arm geometry and different
main/member provenance; they are not presented as different rendered roof shapes.

Compound members, not aggregate bounding boxes, supply ports. The opposite
coincident equal-width middle-port operation uses one shared junction, four ridge
arms and four valleys (8 faces, degree 8). Its independent fixed XYZ witness checks
planarity. Terminal, offset/middle and disjoint narrow branches retain their
independent topology witnesses and metamorphic proofs. No fixture classifier,
Boolean, wavefront or plane-envelope operation is used.

Rectangle meshes support all four roof types. Every evaluated hole-free orthogonal
flat footprint produces one face and consumes artificial cuts. Compound pitched
mesh solve remains unsupported even when its RoofGraph is valid. GeometryProblem
availability does not claim completed SGA21 optimization.

## Migration and proofs

Removed production owners: `roof_building`, `roof_geometry`, `roof_partition`,
`roof_parts`, `roof_planes`, `roof_graph`, `roof_connections`, `roof_features`,
`roof_mesh`, `roof_validation`, binary dependency installation, transitional model
adapters and the independent experimental directory. No compatibility aliases or
runtime fallback remain. Obsolete generator comparison/benchmark/smoke routes and
historical generated roof reports were removed.

Useful rectangle meshes and terminal/middle graph expectations were frozen under
`python/tests/fixtures/`. Independent GEOS/NumPy proofs remain development-only;
the package/runtime use standard Python and Blender. The complete addon API and
mesh adapter are tested in an isolated process rejecting NumPy/Shapely imports.

Classical minimum certificates, exhaustive small MIS/exact-cover oracles, hundreds
of unknown grid footprints, coverage/provenance, seeded invariance and independent
planarity witnesses remain. Noding and reflection indices are checked against
unfiltered predicates. Boundary hit lookup enabled/disabled/cleared produces the
same completions. Performance fingerprints cover every minimum candidate,
retained interpretation, valid/rejected topology and selected seed ID.

## Measurement method

`benchmark_generation.py` uses original U/Cross/residential/Grid14/20/40 fixtures,
11 unprofiled samples after 3 warmups, no persistent cache. Its seed stage tests
four fixed seeds (0, 1, 7, 42); the production call selects once. Batch measurements
repeat the six inputs 1,000 times and distinguish unsupported attempts from
GeometryProblem successes. A separate 1,000-rectangle batch produces final meshes.

The baseline is a detached `db10ea6` checkout with the same canonical candidate
contract before performance changes. Measurements run sequentially on the same
host. `profile_generation.py` separately records nested instrumented stages and
cProfile; these numbers are not interactive performance claims. No candidates,
ambiguity or validity checks are removed for speed.

## Unprofiled results

Python 3.12.14; Linux-6.18.44-x86_64-with-glibc2.41. Baseline runtime SHA `db10ea61c47919474aed8be312ff07e051109b92`; measured updated runtime SHA `a204c56fddc0200b90d9c2bcfdb8a6a1f9742387`. The updated measurement had documentation-only working tree changes.

All times below are median milliseconds. Architecture combines interpretation,
published evaluation and retained part graph construction. Total is measured
directly, so marginal medians need not sum exactly. Seed timing is four selections;
a dash means no valid selectable candidate.

| Input | Partition before → after | Architecture before → after | Topology before → after | Seed before → after | Total before → after | Valid / rejected |
| --- | --- | --- | --- | --- | --- | --- |
| orthogonal_U | 3.805 → 3.161 | 0.675 → 0.563 | 2.267 → 2.175 | — | 7.011 → 6.123 | 0 / 2 |
| cross | 3.002 → 2.849 | 0.668 → 0.528 | 8.842 → 8.544 | 0.045 → 0.046 | 12.978 → 12.714 | 2 / 6 |
| residential_multi_reflex | 5.486 → 4.663 | 0.800 → 0.635 | 1.614 → 1.578 | — | 8.129 → 7.495 | 0 / 1 |
| grid_14 | 17.048 → 17.891 | 5.473 → 5.977 | 2.252 → 2.501 | — | 26.049 → 29.543 | 0 / 38 |
| grid_20 | 41.381 → 25.891 | 10.208 → 7.048 | 2.417 → 1.730 | — | 57.269 → 36.263 | 0 / 23 |
| grid_40 | 249.394 → 163.537 | 69.142 → 56.706 | 34.245 → 13.196 | — | 351.751 → 232.929 | 0 / 896 |

| Batch | Before | After | Result |
| --- | --- | --- | --- |
| 1,000 mixed candidate attempts | 74.837s | 59.697s | 167 GeometryProblems; 833 unsupported; no final compound mesh |
| 1,000 rectangle final meshes | 2.003s | 3.228s | 1,000 validated gable meshes |

Grid40 still misses the single-digit millisecond target. Grid14 and the rectangle
batch regress in these runs; the changes are not claimed to accelerate every
input. No candidate removal or weaker validation compensates for this result.
The 1,000 mixed attempts are not 1,000 generated roofs. Raw samples, p95,
full-family fingerprints and environment metadata are in
[before](canonical/performance-before.json) and [after](canonical/performance-after.json).

## Candidate generation profile

These are nested instrumented observations, not the unprofiled performance
results above. Exclusive time avoids double counting called stages.

| Grid40 stage | Calls | Before exclusive ms | After exclusive ms |
| --- | --- | --- | --- |
| MIS_enumeration | 6 | 0.062 | 0.059 |
| completion_generation | 97 | 52.707 | 28.724 |
| symmetry_detection | 1 | 6.098 | 6.892 |
| symmetry_point_expansion | 320 | 1.266 | 1.667 |
| cut_signature_dedup | 97 | 4.286 | 4.579 |
| noding | 48 | 86.922 | 37.446 |
| face_cycles | 48 | 21.423 | 20.497 |
| subdivision_validation | 48 | 3.318 | 3.702 |
| provenance | 2030 | 13.569 | 11.851 |
| provenance_validation | 48 | 1.371 | 1.772 |
| cell_materialization | 48 | 30.834 | 27.476 |
| subdivision | 48 | 3.220 | 3.436 |

Grid40 has 6 MISs, 97 completion/cut proposals, 48 unique materialized partitions
and 116 work visits. Cut-set deduplication already preceded subdivision; it was
not invented as part of the speedup. This asymmetric fixture has no nonidentity
candidate symmetry expansion; point transform timing belongs to symmetry
detection. Full symmetry expansion remains in the implementation for symmetric
inputs.

The changes reuse first exterior ray hits within one immutable footprint, narrow
noding to conservative coordinate-index windows, narrow reflected-box lookup
with its unchanged exact acceptance test, and reject undefined relation assignments
before member allocation. Every candidate still gets subdivision/minimum/coverage
and provenance validation. Cache contents are not a correctness prerequisite.

Remaining cost is 48 distinct subdivision/Cell materializations and geometric
cycle/provenance work, followed by architectural symmetry evaluation and part
construction. MIS enumeration is negligible. No broad redesign or candidate
pruning is justified by these measurements alone. Detailed probe and cProfile
files are in [canonical/](canonical/).

## Capability and visual results

[Capability diagnostics](canonical/capabilities.json) preserve every original
U/Cross/residential/grid status and the exact unsupported reasons. Cross has
[2 inspected valid graphs](canonical/cross.json), with
[candidate 0](canonical/cross-0.svg) and [candidate 1](canonical/cross-1.svg).
The retained main/branch arrangement is seedable; their physical four-arm equal-width
roof geometry is equivalent. Square gable gives actual perpendicular-ridge mesh
variation: seed 0 `cffcb8c9df7ceec969d180541a6c6fca`, seed 1
`7ae0fafd7ab090134be818e804cb3450`.

Blender 4.3.2 source and installed-ZIP smoke pass. The installed ZIP needs no pip
or binary dependencies. It creates four rectangle types and concave flat mesh,
unwraps UVs, assigns material, checks transformed/nonuniformly scaled input,
finds both square roof axes, exercises the footprint CLI and verifies atomic
compound-solve failure. [Rendered mesh evidence](canonical/blender-meshes.png)
was visually inspected; [smoke report](canonical/blender-smoke.json) records
the generated candidate IDs. Full unittest suite: **99 tests passed**.

## Remaining capabilities

- U/residential/grid gable arrangements lack implemented whole-graph/member
  operations; parallel/partial-end/continuation contacts remain unsupported.
- Compound hip and directional shed topology, and non-orthogonal partitioning,
  remain unsupported.
- SGA21 nonlinear fixed-incidence embedding and solved-mesh validation are not
  implemented for compound pitched candidates. GeometryProblem conversion is
  the current boundary.
- Blender compound pitched mesh output and Geometry Nodes generation remain
  future work; the conversion button currently outputs only supported analytic
  roofs.
