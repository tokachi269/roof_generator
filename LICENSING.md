# Licenses and attribution

Licenses apply by component as listed below. Full texts are available in
[LICENSES/](LICENSES/).

| Component | License |
| --- | --- |
| `addon/roof_generator/**` | **GPL-3.0-or-later**. Copyright tokachi269, 2026. |
| `python/build_addon.py`, `python/blender_smoke_test_addon.py`, `python/tests/test_roof_acceptance.py`, `python/tests/fixtures/roof_acceptance.json` | **GPL-3.0-or-later**. Distribution and acceptance tooling. |
| `python/tests/fixtures/authored_hip/**` | **GPL-3.0-or-later**. Synthetic hip-roof graph. |
| `python/core/**`, `python/blender_adapter.py`, paper-aligned/legacy Python tooling and `python/tests/test_roof_core.py` | **CC BY-NC 4.0**. Research port based on Ren et al. (2021) and related tooling. |
| Runtime dependencies | Their respective licenses in [third-party notices](addon/roof_generator/THIRD_PARTY_NOTICES.md). |

## GPL-3.0-or-later components

The Blender addon implements footprint normalization, RoofPart decomposition,
roof-plane intersections and mesh output. Its source and distribution tooling
are licensed under the GNU General Public License, version 3 or later.

Use and modification, including commercial use, are permitted under the GPL.
Distribution must preserve the applicable copyright and license notices,
provide corresponding source as required, and license covered modifications
under the GPL. See the [full GPL text](LICENSES/GPL-3.0-or-later.txt).

## CC BY-NC 4.0 components

The roof-graph research port implements primal/dual graph processing,
topology queries and planar embedding optimization in Python. It is an
adaptation of the MATLAB implementation; its algorithm and implementation
mapping is documented in [PAPER_ALIGNMENT.md](python/docs/PAPER_ALIGNMENT.md).

**CC BY-NC 4.0 permits noncommercial use, sharing and adaptation. Commercial
use is not permitted under this license.** Sharing requires appropriate
attribution, a link to the license and an indication of modifications.
See the [full CC BY-NC text](LICENSES/CC-BY-NC-4.0.txt).

Attribution:

- **Work:** [Intuitive and Efficient Roof Modeling for Reconstruction and Synthesis](https://arxiv.org/abs/2109.07683).
- **Authors:** Jing Ren, Biao Zhang, Bojian Wu, Jianqiang Huang, Lubin Fan, Maks Ovsjanikov and Peter Wonka.
- **Source:** [Reference implementation](https://github.com/llorz/SGA21_roofOptimization), revision `e9bc3264b787a6cff41a6ed92e39a3e49f3a6e11`.
- **Source license and usage guidance:** [Project README](https://github.com/llorz/SGA21_roofOptimization/blob/e9bc3264b787a6cff41a6ed92e39a3e49f3a6e11/README.md).
- **Adaptation:** Python graph parsing, primal/dual topology tools, SciPy BFGS optimization, research adapters and regression tests. Numerical differences are documented in the paper alignment guide.

## Dependencies

NumPy and Shapely are BSD-3-Clause; GEOS is LGPL-2.1; Blender is GPL.
Redistribution must satisfy each applicable license, including preservation
of notices and LGPL source obligations when distributing GEOS binaries.
Dependency source and license links are in the addon
[third-party notices](addon/roof_generator/THIRD_PARTY_NOTICES.md).
