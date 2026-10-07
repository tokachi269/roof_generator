# Roof Generator — Blender addon

English | [日本語](README.ja.md)

Convert a planar building footprint into one editable Blender roof mesh.
The generator supports concave and oblique footprints, rectangles,
parallelograms, trapezoids and general convex quadrilaterals. L/T/U footprints
are assembled from connected RoofParts. Roof types are **flat, gable, hip and shed**;
ridges, hips and valleys follow roof-plane intersections.

## Installation and use

1. Download [`roof_generator-1.0.0.zip`](packages/roof_generator-1.0.0.zip) using **Download raw file**.
2. In Blender 4.3+, open **Edit → Preferences → Add-ons → Install from Disk**, select the ZIP and enable **Roof Generator**.
3. In addon preferences, use **Install Shapely (Internet)** to set up Shapely when needed. This requires host Python with pip. Set **Host Python with pip** to its executable if automatic detection fails.
4. In Object Mode, select a filled, planar footprint mesh.
5. Open the 3D View sidebar (**N**) → **Roof**, choose the roof type, pitch and eave offset, then press **Generate roof**.

Conversion supports Undo and preserves the input object. **Hide source footprint**
controls its visibility. The output is an ordinary mesh with a UV layer, material
and part/crease attributes, ready for editing and UV unwrapping. Object rotation,
translation and nonuniform scale are supported without applying transforms.

The generated mesh is a roof surface with an intentional perimeter boundary.
Building walls and roof thickness are separate modeling tasks. Holes,
self-intersecting or nonplanar footprints, exhausted decomposition searches,
and unsupported height-step connections produce an explicit error.

## Licenses

| Component | License and conditions |
| --- | --- |
| Blender addon and footprint geometry | **GPL-3.0-or-later**. Commercial use is permitted under the GPL; distribution must satisfy its license and source requirements. |
| Python research port ([Ren et al., 2021](https://arxiv.org/abs/2109.07683)) | **CC BY-NC 4.0**. Noncommercial use only, with attribution, a license link and an indication of modifications. |
| Runtime dependencies | NumPy and Shapely: BSD-3-Clause; GEOS: LGPL-2.1. |

See [LICENSING.md](LICENSING.md) for file scope, attribution and full license texts,
and [third-party notices](addon/roof_generator/THIRD_PARTY_NOTICES.md) for dependency conditions.

## Repository layout

| Path | Purpose |
| --- | --- |
| [`addon/roof_generator/`](addon/roof_generator/) | Blender UI, footprint geometry and mesh output |
| [`packages/`](packages/) | Installable addon ZIP |
| [`python/`](python/README.md) | Build tools, tests, CLI and roof-graph research port |
| [`python/docs/`](python/docs/) | Generator design and paper alignment |
| [`reference/`](reference/README.md) | Source and research references |
| `python/out/`, `dist/` | Generated validation and build artifacts |

## Development and validation

```bash
python -m pip install -r python/requirements.txt
python -m unittest python.tests.test_roof_core python.tests.test_roof_acceptance
python python/build_addon.py
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_addon.py -- --zip dist/roof_generator-1.0.0.zip
```

Validation covers 90 tests, 16 final-mesh acceptance scenarios, all four roof
types, UV/material editing, object transforms, failure without scene mutation,
and addon registration. Representative L/T/U, oblique and residential roofs
are also rendered for visual inspection. CI runs core tests and ZIP checks on
Windows/Linux with Python 3.11/3.13, plus installed-addon tests in Linux Blender
4.3.2. Blender execution is currently validated on Linux.

See the [generator design](python/docs/ROOF_GENERATOR_DESIGN.md) and
[Python guide](python/README.md) for details.
