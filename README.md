# Roof Generator — Blender addon

English | [日本語](README.ja.md)

Generate editable roof surfaces from filled planar footprint meshes in Blender 4.3+.
The core uses minimum rectangular partitions, architectural interpretations and
validated indexed roof graphs. Generation seed selects among equally ranked valid
candidates; unsupported topology produces an explicit error.

## Current capabilities

| Input / roof | Output |
| --- | --- |
| Rectangle, including rotation and square | Gable, hip, shed or flat mesh |
| Hole-free simple orthogonal polygon, including concave outlines | One unified flat roof face |
| Supported terminal/middle gable attachments, disjoint narrow branches, coincident opposite equal-width ports | RoofGraph candidates and a fixed-topology GeometryProblem; compound pitched mesh solve is not implemented |

Arbitrary compound gable/hip/shed roofs and non-orthogonal quadrilateral
partitioning are unsupported. Holes, touching/self-intersecting boundaries,
nonplanar inputs and incomplete searches fail explicitly. A roof surface has an
intentional perimeter boundary; walls and thickness are separate modeling tasks.

Distinct receiver-end terminal attachments, including the U fixture, compose
into one gable RoofGraph. The [support audit](python/docs/RELATION_TOPOLOGY_SUPPORT.md)
reports all candidate rejection causes separately from final mesh capabilities.
Parallel, offset/width-step continuation and partial-end contacts still require
implemented topology operations.

## Installation and use

1. Download [`roof_generator-1.2.0.zip`](packages/roof_generator-1.2.0.zip) with **Download raw file**.
2. Use **Edit → Preferences → Add-ons → Install from Disk**, then enable **Roof Generator**.
3. Select filled planar footprint meshes in Object Mode.
4. Open the sidebar (**N**) → **Roof**, set type, pitch, eave offset and seed, then **Generate roofs**.

No pip installation or third-party wheels are needed. Output is one ordinary mesh
object per footprint, with shared vertices, UVs, material and `roof_cell_i` /
`roof_feature_i` provenance attributes. Rotation, translation and nonuniform
scale are supported without applying transforms. Batch conversion validates all
inputs before changing the scene. The conversion button supports Undo; it is not
a Geometry Nodes implementation.

The same footprint, settings and seed reproduce the same selected candidate.
Blender uses the source object's local reference direction. For coordinate API
calls, rotate `reference_direction` with the footprint to preserve physical seed
choices. This explicit reference resolves the rotational ambiguity of perfectly
symmetric outlines.

## Architecture and development

See [ARCHITECTURE.md](ARCHITECTURE.md), [tools and tests](python/README.md),
[research mapping](python/docs/ROOF_PART_INTERPRETATION_RESEARCH.md), and
[canonical measurements](python/docs/CANONICAL_EVALUATION.md).

```bash
python -m pip install -r python/requirements.txt  # development oracles only
python -m unittest discover -s python/tests
python python/build_addon.py
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test.py -- --zip dist/roof_generator-1.2.0.zip
```

`addon/roof_generator/core/` owns the pipeline. `addon/roof_generator/` contains
Blender adapters; `python/` contains inspection, measurements and tests;
`packages/` contains the installable ZIP. Source/research references are under
[reference/](reference/README.md).

## License

Source, tools and tests are **GPL-3.0-or-later**. Commercial use is permitted;
distribution must satisfy the GPL's license and source requirements. Runtime
requires only Blender and Python's standard library. Development-only NumPy and
Shapely/GEOS have their own license conditions. See [LICENSING.md](LICENSING.md)
and [third-party notices](addon/roof_generator/THIRD_PARTY_NOTICES.md).
