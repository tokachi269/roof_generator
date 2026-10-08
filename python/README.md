# Python development

The Blender addon is documented in [the root README](../README.md).
Its geometry source is `../addon/roof_generator/core/`, with mesh input and output
modules in the addon package. CLI conversion uses the same addon code.

## Licenses

[LICENSING.md](../LICENSING.md) defines the file scope and conditions.
The source, CLI, tests and build tooling are **GPL-3.0-or-later**, permitting
commercial use under the GPL and subject to its distribution/source requirements.

## Core tests and build

Run from the repository root:

```bash
python -m pip install -r python/requirements.txt
python -m unittest discover -s python/tests
python python/build_addon.py
```

The ZIP contains the addon source, documentation and license text. Relative path
ordering, timestamps and file metadata are fixed for reproducible Windows/Linux
builds. The committed `packages/roof_generator-1.1.0.zip` must match the builder
output. To refresh it:

```bash
python python/build_addon.py --output packages/roof_generator-1.1.0.zip
```

## Actual installed-addon smoke

```bash
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_addon.py -- --zip dist/roof_generator-1.1.0.zip
```

This installs the portable ZIP into Blender's user scripts, enables it, invokes
the dependency-install and conversion operators, exercises all 16 final-mesh
fixtures, all four types, UV unwrap/materials, a tilted/scaled million-unit
translation, failure without scene mutation, and disable/re-enable lifecycle.
It saves `python/out/addon/addon_roofs.blend` and `report.json`. Use a disposable
Blender user profile when running the smoke. `BLENDER_USER_SCRIPTS` can isolate
its installed-addon directory. It requires host Python with pip and network access
for the explicit install-dependency test; pass `--host-python /path/to/python`.
The source-object smoke validates the footprint CLI and renders representative roofs:

```bash
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_roof.py -- --output-dir python/out/acceptance
```

## Dependency installation outside the UI

```bash
python python/install_roof_dependencies.py --blender blender
```

Default target is the source addon, `addon/roof_generator/.roof-deps/cpNNN`.
For an installed addon, pass `--addon-dir` with the installed package directory.
The command queries Blender's CPython and uses a host pip to install a matching
binary Shapely wheel without modifying system packages. NumPy is bundled with
Blender. The panel's Install dependency button performs the same matching-wheel
operation for the running Blender and its installed package path.

## Optional source CLI and core API

```bash
blender building.blend --python python/blender_generate_roof_from_footprint.py -- --object-name Footprint --roof-type gable --pitch 0.5
```

The geometry library also works outside Blender. Add `addon/` to your import path
and import `roof_generator.core.roof_building.generate_roof` and
`roof_generator.core.roof_parts.RoofParameters`. Importing the addon package does
not register UI classes or require bpy until `register()` is invoked.
`generate_roof` returns the indexed XY RoofGraph, its constrained 3D embedding,
RoofParts/adjacency/provenance, classified creases and a validated ordinary mesh. Part overrides remain available.

See [ROOF_GENERATOR_DESIGN.md](docs/ROOF_GENERATOR_DESIGN.md) for decomposition,
plane connections, topology and acceptance validation, and
[research references](../reference/README.md) for the source literature.

## Performance and city generation

```bash
python python/benchmark_roof.py --samples 11 --warmup 2
python python/benchmark_city.py --buildings 1000
blender -b --factory-startup --python-exit-code 1 --python python/benchmark_city.py -- --blender-objects --buildings 1000
```

The conversion button processes all selected footprint meshes in one batch.
For scripted batches, pass `RoofRequest(source, RoofParameters(...))` instances
to `roof_generator.blender_output.generate_objects`. Requests may have different
roof types/pitches. The adapter evaluates inputs once and validates every roof
before output. `generate_object` uses the same route for a single footprint.

Measurements and limits: [ROOF_PERFORMANCE.md](docs/ROOF_PERFORMANCE.md).

## Independent graph-first evaluation

`graph_first/` owns a separate, plane-free topology path. It generates rectangle
gable/hip/shed/flat meshes analytically and composes **pre-solver 2D graphs**
for a terminal gable attachment, narrow/equal-width middle attachments, and
separated narrow middle branches on one host. It is not wired into the addon
conversion button. U/cross junctions, arbitrary architectural aggregation,
multi-cell geometry solving and oblique cells remain unsupported; no automatic
substitution by the existing generator occurs. The roof-independent partition layer handles arbitrary
reflex counts in hole-free simple orthogonal polygons, with a classical minimum
rectangle-count certificate.

```bash
python python/inspect_roof_graph.py --fixture orthogonal_L --output python/out/graph-first/L.json
python python/inspect_roof_graph.py --fixture rectangle_gable --roof-type hip
python python/benchmark_graph_first.py --samples 101 --warmup 5
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_graph_first.py
```

Inspection exports cell boundaries/adjacency, primitive/composed RoofGraphs,
edge meanings/provenance, an SGA21-ready geometry problem and an SVG. The drawing
is a disposable initializer, not a solved L roof. The benchmark separates
analysis, decomposition, graph construction, geometry and mesh export and
compares the unchanged reference generator. New core modules require only the
Python standard library; the comparison/tests use the existing dependencies.
See [the design](docs/GRAPH_FIRST_DESIGN.md) and
[the evaluation](docs/GRAPH_FIRST_EVALUATION.md) for evidence and limits.

## Generic minimum rectangular partition

```bash
python python/inspect_rectangle_partition.py --fixture residential_multi_reflex
python python/inspect_rectangle_partition.py --fixture comb_40 --output python/out/partition/comb.json
python python/inspect_rectangle_partition.py --input footprint.json
python python/benchmark_rectangle_partition.py --samples 101 --warmup 5 --buildings 1000
```

`footprint.json` is an ordered XY point array or an object with a `footprint`
array. The scalar API is `analyze(points)` followed by `cells.decompose(footprint)`;
it returns Cells, shared intervals, exterior provenance and a certificate with
all good diagonals, conflicts, maximum matching, selected independent set,
completion cuts and minimum count. It takes no roof parameters and imports no
Shapely, NumPy, roof composition or geometry solver.

The inspection JSON/SVG shows the selected diagonals and completed partition.
The test-only grid generator supplies unknown inputs and is not imported by the
partition core. The benchmark measures actual uncached partition stages and
1000 distinct geometries; input generation is excluded explicitly. See the
[algorithm contract](docs/MINIMUM_RECTANGULAR_PARTITION.md) and
[partition evaluation](docs/RECTANGULAR_PARTITION_EVALUATION.md), including the
necessary symmetry qualification for ambiguous intrinsic axes. The existing
terminal-graft proof remains. Scoped composition does not change this
partition's roof-independent contract.

## Published branch/junction composition

```bash
python python/inspect_roof_composition.py --fixture orthogonal_T
python python/inspect_roof_composition.py --input footprint.json --output python/out/composition/building.json
```

Read [the research reassessment](docs/ROOF_COMPOSITION_RESEARCH.md) for the
published mechanisms, prior rejected junctions, Cell/port mapping and explicit
adaptations. `Composition.connections` records applied operations. Inspection
schema 2 has plural connections, replacing the prototype's single connection.
The three-panel SVG separates cells/cuts/adjacency, primitive candidates and
final retained ridge/valley/hip/junctions. Unsupported inspection writes an
explicit reason with no final graph and exits 2. Independent gables are never
returned as a fallback. XY is a drawing seed; this does not solve a multi-cell
roof or generate its final Blender mesh. Nonlinear solving remains separate.
