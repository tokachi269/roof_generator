# Third-party notices

Roof Generator: copyright tokachi269, 2026; **GPL-3.0-or-later**.
The complete license text is in [LICENSE](LICENSE).

## Runtime

The addon uses Python's standard library and the Blender API.
Blender is GPL: https://www.blender.org/about/license/.

The bundled `vendor/straight_skeleton` source is adapted from
`py_straight_skeleton` 0.1.0, copyright ICON, 2024, under BSD-3-Clause.
Its original license is included at [vendor/straight_skeleton/LICENSE](vendor/straight_skeleton/LICENSE).
Only algorithm/math source is shipped; plotting and wheel metadata are omitted.
No runtime pip installation or external wheels are required.

## Development-only independent test oracles

| Dependency | License | Source / license |
| --- | --- | --- |
| NumPy | BSD-3-Clause | https://numpy.org/doc/stable/license.html |
| Shapely 2.1.2 | BSD-3-Clause | https://github.com/shapely/shapely/blob/2.1.2/LICENSE.txt |
| GEOS, dynamically loaded by Shapely | LGPL-2.1 | https://libgeos.org/usage/download/ |

Redistribution must satisfy each dependency's license, including preservation
of notices and LGPL source obligations when distributing GEOS binaries.
