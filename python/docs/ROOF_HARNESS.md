# Roof semantic harness and dependency boundary

## Scope and contract

The harness observes the public `generate_roof` route and Blender output. It
checks the indexed RoofGraph, affine embedding, final mesh and failure behavior.
Independent analytic/topological proofs are primary; frozen semantic snapshots
provide differential evidence across implementation changes.

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
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_addon.py -- --zip packages/roof_generator-1.1.0.zip --output-dir python/out/harness/addon
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
The current runtime is:

```text
UI -> blender_output.generate_objects -> one evaluated-input snapshot
  -> mesh_input.generate_footprint_mesh -> roof_building.generate_roof
     -> normalize_footprint
     -> decompose -> ring/chord search -> winning RoofParts/adjacency
     -> connect -> support inequalities -> line intervals -> indexed RoofGraph
     -> affine graph embedding -> n-gon/optional hole tessellation
     -> validate_mesh -> topology/planarity + independent projection/perimeter checks
  -> ordinary Blender mesh objects / UV / materials
```

Candidate rings and support-line graphs use no polygon Boolean operations.
Shapely remains for input validity, winning-part provenance/adjacency, independent
mesh validation and constrained triangulation of holes. These checks remain
active; a cache hit never bypasses the final validator.

Partition caches are keyed by normalized geometry, provenance, type and limits.
Graph caches are keyed by geometry and relative plane constraints. Common
positive vertical scaling and translation restore the current requested pitch,
eave heights, explicit planes and part metadata. Invalid requests are checked
before cache access. Different relative part constraints rebuild the graph.

See [ROOF_GENERATOR_DESIGN.md](ROOF_GENERATOR_DESIGN.md) for the geometry contracts
and [ROOF_PERFORMANCE.md](ROOF_PERFORMANCE.md) for current measured performance.
