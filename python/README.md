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
builds. The committed `packages/roof_generator-1.0.0.zip` must match the builder
output. To refresh it:

```bash
python python/build_addon.py --output packages/roof_generator-1.0.0.zip
```

## Actual installed-addon smoke

```bash
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_addon.py -- --zip dist/roof_generator-1.0.0.zip
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

## Native base-mesh smoke and editable demo

```bash
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_base_mesh.py
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_base_mesh.py -- --zip packages/roof_generator-1.0.0.zip
```

Runs without Shapely, checks 224 dimension/seed combinations for one connected
face component, one manifold boundary loop, Euler characteristic 1, upward
normals and planar 1m cells. Checks live updates, seed determinism, shared node
groups and modifier application. Saves an editable 16-object demo, preview and
timing report under `python/out/base_meshes/`. Timings include mesh validation.
Also checks 64 seed/height combinations: fractional Height, closed manifold
wall/bottom/top extrusion, volume = area * height, and the planar Roof Base
output with unchanged 1m footprint. Height zero preserves the original disk.
The saved demo shows raised building bases; roof surfaces are not generated.
The ZIP variant also checks installation and disable/re-enable lifecycle;
isolate `BLENDER_USER_SCRIPTS` as with the roof addon smoke.

## Base meshes with existing roof generation

```bash
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_base_roof.py
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_base_roof.py -- --installed
blender --factory-startup --python-exit-code 1 --python python/blender_smoke_test_base_roof_live.py
blender --factory-startup --python-exit-code 1 --python python/blender_smoke_test_base_roof_live.py -- --asset
```

The roof smoke checks all four types against independent rectangular geometry
and volumes, compares multipart roof faces and feature attributes to the
existing generator, checks closed envelopes, stale-cache rejection, unsupported
inputs, and Roof/Height changes without rebuilding. It saves an editable
16-building roof demo and render under `python/out/base_roofs/`.
The live smoke runs in Blender's UI event loop, changes dimensions/pitch, and
verifies automatic generation without manually invoking the update callback.
The `--asset` case removes the creation operator's object tag and verifies that
an ordinary mesh using the group still receives automatic roof updates.
It also verifies native Height and Roof OFF changes, writes `live_report.json`,
and quits its own Blender instance. Both require the existing Shapely dependency.
The `--installed` variant uses the already installed addon and dependency in
the disposable profile, and checks disable/re-enable of the update handlers.

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
`generate_roof` returns connected planar regions, RoofParts/adjacency/provenance,
classified creases and a validated ordinary mesh. Part overrides remain available.

See [ROOF_GENERATOR_DESIGN.md](docs/ROOF_GENERATOR_DESIGN.md) for decomposition,
plane connections, topology and acceptance validation, and
[research references](../reference/README.md) for the source literature.
