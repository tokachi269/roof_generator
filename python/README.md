# Python development and SGA21 research port

The Blender addon is documented in [the root README](../README.md).
Its geometry source is `../addon/roof_generator/core/`, with mesh input and output
modules in the addon package. CLI conversion uses the same addon code.

## Licenses

[LICENSING.md](../LICENSING.md) defines the file scope and conditions.
The addon and its acceptance/build tooling are **GPL-3.0-or-later**, permitting
commercial use under the GPL and subject to its distribution/source requirements.
The SGA21-derived optimizer, topology port and research adapters are
**CC BY-NC 4.0**: noncommercial use only, with attribution, a license link and
an indication of modifications.
`tests/fixtures/authored_hip/` defines a synthetic hip-roof graph.

## Core tests and build

Run from the repository root:

```bash
python -m pip install -r python/requirements.txt
python -m unittest python.tests.test_roof_core python.tests.test_roof_acceptance
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
The source-object/render smoke also remains available:

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
blender building.blend --python python/blender_generate_roof_from_footprint.py -- --object-name Footprint --roof-kind gable --pitch 0.5
```

The geometry library also works outside Blender. Add `addon/` to your import path
and import `roof_generator.core.roof_building.generate_roof` and
`roof_generator.core.roof_parts.RoofParameters`. Importing the addon package does
not register UI classes or require bpy until `register()` is invoked.
`generate_roof` returns connected planar regions, RoofParts/adjacency/provenance,
classified creases and a validated ordinary mesh. Part overrides remain available.

## Noncommercial SGA21 optimizer CLI

```bash
python python/run_primal_roof.py python/tests/fixtures/authored_hip/sample --output python/out/authored_hip.json
```

This optimizes the embedding of an explicitly specified roof graph. See
[PAPER_ALIGNMENT.md](docs/PAPER_ALIGNMENT.md) for MATLAB anchors and approximation
limits, and [ROOF_GENERATOR_DESIGN.md](docs/ROOF_GENERATOR_DESIGN.md) for the separate
addon generator. Role/cell preview modules provide research comparisons.
