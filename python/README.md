# Python development and SGA21 research port

The installed Blender addon is documented in [the root README](../README.md).
Its canonical geometry source is `../addon/roof_generator/core/`, with independent
mesh input and output modules in the addon package. The former copies under
`python/core/` are removed. CLI conversion delegates to the same addon code.

## Licenses

[LICENSING.md](../LICENSING.md) defines the component boundaries. The new addon
and its acceptance/build tooling are GPL-3.0-or-later. The retained SGA21-derived
optimizer, topology port and historical adapters are CC BY-NC 4.0 research code;
they are excluded from the addon ZIP and are not relicensed by new commit metadata.
No upstream source files or datasets remain. The four graph input files under
`tests/fixtures/authored_hip/` are a newly specified hip roof rather than copies
of the upstream Fig.7 sample.

## Core tests and build

Run from the repository root:

```bash
python -m pip install -r python/requirements.txt
python -m unittest python.tests.test_roof_core python.tests.test_roof_acceptance
python python/build_addon.py
```

The ZIP is reproducible: sorted files, fixed timestamps and no dependency wheels,
caches or optimizer modules. The committed `packages/roof_generator-1.0.0.zip`
must match the builder output. To refresh it:

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

This remains the attributed paper-aligned path for an already specified roof
graph. It does not infer final roof topology. See
[PAPER_ALIGNMENT.md](docs/PAPER_ALIGNMENT.md) for MATLAB anchors and approximation
limits, and [ROOF_GENERATOR_DESIGN.md](docs/ROOF_GENERATOR_DESIGN.md) for the separate
addon generator. Historical role/cell preview modules are regression research
material, not dependencies of the addon or its geometry.
