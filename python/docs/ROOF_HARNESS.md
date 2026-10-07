# Roof semantic harness and dependency boundary

## Scope and contract

Milestone 1 observes the existing public `generate_roof` and Blender adapter.
It does not change partition selection, roof support propagation, clipping,
tessellation, validation, dependency installation or runtime imports. No new
production abstraction or test-only state is introduced. The earlier uncommitted
base-mesh Geometry Nodes feature is outside this milestone's commit.

The preserved product contracts are: a finite simple planar footprint is
normalized without turning oblique edges into orthogonal ones; its selected
convex roof parts preserve exterior provenance and shared-boundary adjacency;
exposed affine roof planes produce one continuous upward planar mesh disk with
the same projection/perimeter; geometric creases retain ridge/hip/valley/eave/
gable_end meaning. Unsupported geometry/parameters/search exhaustion raise
`UnsupportedRoofError`, rather than repair the input or emit a partial mesh.
Partition count alone is not equivalent roof semantics: current selection also
uses aspect, cut length, direction and geometric signatures.

These contracts are the specification. Fixtures and implementation output are
evidence, not the source of correctness. The approach follows the independent
oracle and focused-to-regression principles in wire's
[`agent_harness.md`](https://github.com/tokachi269/wire/blob/main/docs/engineering/agent_harness.md),
[`testing.md`](https://github.com/tokachi269/wire/blob/main/docs/testing.md) and
[`wire/testing.md`](https://github.com/tokachi269/wire/blob/main/docs/wire/testing.md).
No wire framework is copied.

## Proofs and equivalence

| Contract | Direct evidence |
| --- | --- |
| Rectangle gable/hip height, slopes and ridge | Independent 12x6 distance-to-edge equations; pitch 0.5, eave 2; ridge at y=3, z=3.5; gable x=0..12, hip x=3..9 |
| Exposed planar surfaces / coverage | 2 gable faces or 4 hip faces, each on an analytic support plane; independent Shapely development oracle compares projected faces with the rectangle; area 72, perimeter 36, no overlapping faces |
| One topological disk | Independent face incidence, consistent winding, connected faces, one closed boundary, manifold vertex fans, Euler characteristic 1 |
| Feature semantics | One ridge with analytic endpoints, eaves at z=2, correct gable_end or hip feature family |
| Proof can detect faults | Height displacement, ridge-to-valley misclassification and missing face are each rejected by the Primary proof |
| Existing nonrectangular behavior | Secondary baseline generated from archived starting SHA, not from the proposed implementation; all 16 acceptance cases, extra quad types, directional ambiguity and 7 failures |
| Rigid/representation invariance | Full semantic snapshots for translation/rotation/collinear subdivision; cyclic/winding checks on all acceptance inputs, with the directional limitation below explicitly detected |
| Exterior provenance | Each recorded original input edge is collinear with and contained in its normalized parent exterior segment; part subsegments lie on the same parent; no input identity is lost |

`roof_harness.py` reads normalized footprint, part boundaries/adjacency/exterior
provenance/planes, exposed regions including holes, final vertices and oriented
face loops with owners, every classified mesh feature, projected area, perimeter
and unsupported failure class. It does not compute expected roof decisions.

For comparison, known rigid transforms are undone, coordinates/heights are put
in unit-perimeter reference axes, and part/vertex IDs become geometric order.
This avoids intrinsic-frame symmetry ties being mistaken for geometry changes.
Region rings remove redundant straight-edge waypoints within 5e-9 normalized
distance; exported mesh face incidence, feature edges and winding are retained.
Floating coordinates/slopes use absolute 5e-8 tolerance; metric area/perimeter
use 5e-8 * max(1, magnitude). Counts/indices/labels compare exactly. Rounding to
7 decimals orders data only; original doubles are compared. Original source IDs
and raw intrinsic rings remain diagnostics because input subdivision/permutation
changes those identities legitimately. The separate provenance proof checks them.

**Known baseline limitation:** `rectangle_shed` with automatic direction reverses
its downhill side after a cyclic shift by two vertices. The slope changes from
`z=0.5*y` to `z=0.5*(6.2-y)`. Winding reversal passes on all 16 fixtures; cyclic
equivalence passes on 15 and this one real difference is recorded, not reported
as a passing invariance. A directionless symmetric rectangle cannot choose a
unique shed orientation while also guaranteeing equivariance under all its
rotational symmetries. An explicit direction/selection contract must be decided
before changing that behavior. No expectedFailure/skip or production repair is
used to hide the difference. Its shifted result is also in the baseline.

## Commands

From repository root, with the existing development requirements installed:

```powershell
python -m unittest discover -s python/tests -p test_roof_harness.py
python python/roof_harness.py --reference python/tests/fixtures/roof_semantic_baseline.json
python python/benchmark_roof.py --samples 11 --warmup 2 --profile python/out/harness/residential.pstats
python python/audit_roof_overlay.py
python -m unittest discover -s python/tests
```

For an independent old/new comparison, archive the chosen baseline addon into a
separate directory, capture it in a **fresh process** with
`--addon-dir <baseline-addon-directory> --output <baseline-json>`, then compare
the current route with `--reference <baseline-json>`. Do not regenerate a frozen
baseline to make a failed production replacement pass.

Blender (use the actual installed executable):

```powershell
blender -b --factory-startup --python-exit-code 1 --python python/blender_benchmark_roof.py -- --samples 11 --warmup 2
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_addon.py -- --zip packages/roof_generator-1.0.0.zip --output-dir python/out/harness/addon
```

The installed-addon smoke explicitly installs the existing dependency. Set
`BLENDER_USER_SCRIPTS` to a disposable directory, as in the main Python README.
It is regression evidence, **not** evidence of pip-free installation.

## Measurements and call graph

`benchmark_roof.py` temporarily wraps the five orchestration references used by
the actual public call. It never copies the generation algorithm or disables
validation. The remaining time includes parameter/frame/world-output work.
`cold_rebuild` clears all five bounded geometry/partition caches before every
sample, outside timing; two warmups still warm imports/CPU/GEOS. `warm_partition`
retains caches and measures repeated identical geometry requests. It is not an
end-to-end interactive UI latency guarantee. Both modes retain all roof work.
11 unprofiled samples give median/p95, with raw samples and runtime versions.
Blender measures the same stages plus adapter input extraction/validation and
mesh creation/UV/materials separately. It also retains full core validation.
Profiler call counts are separate diagnostic evidence, never benchmark timings.

Recorded reports are under [baselines/](baselines/). Absolute elapsed times are
machine/run dependent; no speedup or 10ms goal is claimed by this milestone.
The runtime graph remains:

```text
UI -> blender_output.generate_object -> mesh_input.generate_footprint_mesh
  -> roof_building.generate_roof
     -> normalize_footprint
     -> decompose -> recursive solve -> _candidate_cuts -> ray predicates/split
     -> connect -> primitive/plane_patches -> clip/overlay -> region_features
     -> tessellate -> boundary noding/welding/optional hole triangulation
     -> validate_mesh -> topology/planarity + projection/perimeter overlay
```

## Shapely classification and next boundary

| Class | Existing responsibility | Assessment |
| --- | --- | --- |
| A: small geometry | signed area/cross, ring cleanup, convex/reflex, affine plane evaluation | Already self-computed; the input/return containers are still Shapely polygons. Extracting them again contributes little. |
| A | normalized exterior provenance distance predicates; point-in-simple-polygon; ray/boundary hits; simple ring split at a known chord; convex half-plane clipping | Replaceable with small explicit numerical contracts. Current `clip` builds a half-plane polygon, then invokes generic intersection. Ray/split robustness near vertices and collinear boundaries needs differential coverage. |
| B: algorithm/representation | recursive candidate `split` + union/symmetric-difference validation; part adjacency/source overlays | Use ordered rings and known chords/shared segments, preserving the current selection policy before attempting a different partition algorithm. |
| B | completed support domains; all-pairs patch intersection/difference; by-plane union; continuity/features | Prefer convex pieces plus line/half-plane arrangements and shared topology. Do not build a general-purpose Boolean API. |
| B | tessellation boundary unary_union noding and independent validation overlays; adapter source face union | Consume explicit shared planar topology and prove coverage/embedding with independent invariants. Validation must remain active throughout replacement. |
| C: robust topology currently delegated to GEOS | disconnected intermediate visible regions, numerical slits, optional exposed holes and constrained hole triangulation | Existing representation needs robust handling, but the mandatory fixtures do **not** establish that a general Boolean engine is inherently necessary after a representation change. |

`audit_roof_overlay.py` observes all 16 mandatory fixtures. Every completed
support domain in those cases is convex and no final exposed region has a hole.
Intermediate `difference` returns MultiPolygons for L/U/rotated_L/oblique_L/
unequal-width/residential cases. Unequal-width and terminating-ridge intermediate
holes have normalized area about 1.7e-13: these are precision-sensitive artifacts,
not evidence of intentional courtyard capability. Do not infer that hole export
can be deleted: explicit plane/part overrides are broader than this audit, and
the current tessellator has a real hole branch. Its necessity outside mandatory
fixtures remains unproven. Retain it until the replacement has equivalent proof.

The next most effective **cold-generation** boundary is `_candidate_cuts`: replace
generic ray intersection/split with direct ray hits and splitting a simple ring
at a known chord, while keeping the current recursive search/cost. The profile
locates most decomposition time there. Risks: oblique rays, hits at vertices,
collinear boundary overlap, winding/source identities, and slightly altered
candidate endpoints changing the selected partition and ridge/valley layout.
Primary topology/coverage proofs plus the entire semantic differential must
guard that change. Merely minimizing rectangle count is insufficient.

After that, `connect`'s visibility representation is the next runtime-removal
boundary: it runs on every roof and dominates uncached downstream/warm work.
Convex support domains in the observed cases make half-plane arrangements worth
evaluating, but do not prove all accepted overrides will have convex domains.

Milestone 2 is not implemented here: the cheap primitive owners already exist,
and a cosmetic primitive extraction cannot remove the pervasive Polygon/
overlay/noding/validation runtime dependency. The meaningful next cut spans
candidate topology and its proof obligations; doing it as an unmeasured tiny
primitive patch would conceal that scope. Milestone 3/connection redesign and
runtime-dependency removal are deliberately not attempted. Shapely/GEOS, host
pip installation UI and `.roof-deps` remain until all clean-install, acceptance,
semantic, Blender and failure gates are satisfied.
