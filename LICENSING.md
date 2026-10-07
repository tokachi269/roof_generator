# License scope and provenance

This repository contains components with different licenses. Removing upstream
files, rewriting Git history, or detaching the GitHub fork does not change the
rights in code derived from an earlier work. No permission from the SGA21 authors
to relicense their code or use it commercially has been obtained.

| Component | License / provenance |
| --- | --- |
| `addon/roof_generator/**` | **GPL-3.0-or-later**. Newly written plane-based footprint generator, Blender UI, independent mesh projection and import. Copyright tokachi269, 2026. |
| `python/build_addon.py`, `python/blender_smoke_test_addon.py`, `python/tests/test_roof_acceptance.py`, `python/tests/fixtures/roof_acceptance.json` | GPL-3.0-or-later; newly authored distribution and acceptance tooling. |
| `python/core/**`, `python/blender_adapter.py`, the retained paper-aligned/legacy Python tooling and `python/tests/test_roof_core.py` | **CC BY-NC 4.0** for the SGA21-derived material. These are the attributed MATLAB-to-Python research port and related legacy tools, not part of the addon ZIP. Their original noncommercial conditions are retained. |
| `python/tests/fixtures/authored_hip/**` | Newly specified synthetic graph, GPL-3.0-or-later. No upstream example or dataset file is copied. |
| External dependencies | Their own licenses, listed in [addon third-party notices](addon/roof_generator/THIRD_PARTY_NOTICES.md). |

## Independent addon

The addon implements the architecture documented in
[ROOF_GENERATOR_DESIGN.md](python/docs/ROOF_GENERATOR_DESIGN.md): geometric
normalization, architectural RoofParts, affine roof planes, exposed-surface
intersection and shared mesh topology. Its geometry modules were written for this
project; they are not a translation of the SGA21 objective or MATLAB source.
The new addon plane projection and Blender mesh import do not import the research
adapter, optimizer, source datasets or historical Blender utilities.

The build script packages **only** `addon/roof_generator/`, excluding local wheels
and generated caches. The installed-ZIP smoke test also verifies that no legacy
`core` optimizer module is imported. GPL attribution, license text and notices are
included in the ZIP. These facts apply to the addon, not to the entire repository.

[Blender's licensing guidance](https://www.blender.org/about/license/) requires
published scripts using its Python API to use a GPL-compatible license. We do not
place the CC BY-NC research port in this addon or claim that it has become GPL.

## SGA21 research port

Source: [llorz/SGA21_roofOptimization](https://github.com/llorz/SGA21_roofOptimization),
upstream revision `e9bc3264b787a6cff41a6ed92e39a3e49f3a6e11` inspected during
development. Paper: [Intuitive and Efficient Roof Modeling for Reconstruction
and Synthesis](https://arxiv.org/abs/2109.07683), Jing Ren, Biao Zhang, Bojian Wu,
Jianqiang Huang, Lubin Fan, Maks Ovsjanikov and Peter Wonka.

The original work is offered under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
The original README also asks users to contact its authors for commercial uses
or derivatives. Its stated contacts are jing.ren@kaust.edu.sa,
peter.wonka@kaust.edu.sa and maks@lix.polytechnique.fr. The standard license
permits compliant noncommercial adaptations; commercial use requires separate
permission. The retained port must not be advertised as unrestricted commercial
software merely because its commit history has changed.

Changes include Python primal/dual graph parsing, topology queries, the SciPy
BFGS port, Blender research adapters, regression tests, and isolation of legacy
cell previews. The optimizer's approximation differences are recorded in
[PAPER_ALIGNMENT.md](python/docs/PAPER_ALIGNMENT.md). All upstream MATLAB, UI,
dataset and historical utility files and copied Fig.7 inputs have been removed;
their source is linked in [reference/README.md](reference/README.md).

The full license texts are in [LICENSES/](LICENSES/). No blanket MIT or GPL license
is assigned to SGA21-derived material. Patents, trademarks and rights beyond the
licenses' scope are not granted by this notice.
