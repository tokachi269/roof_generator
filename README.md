# Roof Generator — Blender addon

English | [日本語](README.ja.md)

Generate editable roof surfaces from filled planar footprint meshes in Blender 4.3+.
Orthogonal gables use region-guided exterior end choices and one continuous
polygon roof model. Mathematical rectangle cuts are not independent roofs.
Generation seed selects among fully validated
candidates; unsupported topology produces an explicit error.

## Current capabilities

| Input / roof | Output |
| --- | --- |
| Rectangle, including rotation and square | Gable, hip, shed or flat mesh |
| Hole-free simple orthogonal polygon, including concave outlines | One unified flat roof face |
| Supported simple orthogonal footprints, including offset bands and branch networks | One solved continuous gable roof; hip facets can remain |
| Convex parallelogram, trapezoid or general quadrilateral | Gable, shed or flat mesh; gable directions vary by seed |
| Supported simple polygons at arbitrary angles, including concave outlines | Hip mesh with all exterior edges as eaves |
| Supported nonorthogonal compound footprints with opposed-support terminal caps | One mixed gable/hip mesh; maximal compatible gable-end sets are seeded |

Unresolved polygon events, nonterminal/partial or nonparallel-support compound
gable ends and compound shed roofs are unsupported. Holes, touching/self-intersecting boundaries,
nonplanar inputs and incomplete searches fail explicitly. A roof surface has an
intentional perimeter boundary; walls and thickness are separate modeling tasks.

Roof junctions are constructed globally before fixed embedding.
The [staged coverage report](python/docs/END_TO_END_EVALUATION.md) separates
RoofGraph availability from actual solve, validated mesh and Blender conversion.
Connected-grid stress is one corpus, not overall coverage. Unresolved polygon
events, finite gable-end model coverage and incomplete searches remain limits.
Fully declared face planes use a linear fixed-topology embedding; the generic
covariance optimizer remains for problems with unspecified planes. See
[embedding performance and proofs](python/docs/PLANE_EMBEDDING.md).
See [arbitrary-angle scope and measured outcomes](python/docs/ARBITRARY_ANGLE_ROOFS.md)
for separate hip, terminal-gable and single-quadrilateral corpora. The terminal
model requires opposed neighboring eave supports and triangular cap incidence;
it does not infer a gable from every parallel edge pair.

## Installation and use

1. Download [`roof_generator-1.5.0.zip`](packages/roof_generator-1.5.0.zip) with **Download raw file**.
2. Use **Edit → Preferences → Add-ons → Install from Disk**, then enable **Roof Generator**.
3. Select filled planar footprint meshes in Object Mode.
4. Open the sidebar (**N**) → **Roof**, set type, pitch, eave offset and seed, then **Generate roofs**.

To replace an existing installation, remove the addon in Preferences before
installing the ZIP; Blender's overwrite installation can retain removed files.

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
[canonical measurements](python/docs/END_TO_END_EVALUATION.md).

```bash
python -m pip install -r python/requirements.txt  # development oracles only
python -m unittest discover -s python/tests
python python/build_addon.py
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test.py -- --zip dist/roof_generator-1.5.0.zip
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

Native base generation is available at **View3D > Sidebar > Building > Create
Base Meshes**. The modifier keeps editable dimensions, seed, height and a Roof
toggle. Roof generation uses the canonical Python API; an unsupported roof
keeps the native base and walls visible.
