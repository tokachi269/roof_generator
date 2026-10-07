# Third-party notices

Roof Generator: copyright tokachi269, 2026; **GPL-3.0-or-later**.
The complete license text is in [LICENSE](LICENSE).

## Runtime dependencies

| Dependency | License | Source / license |
| --- | --- | --- |
| NumPy, provided with Blender | BSD-3-Clause | https://numpy.org/doc/stable/license.html |
| Shapely 2.1.2 | BSD-3-Clause | https://github.com/shapely/shapely/blob/2.1.2/LICENSE.txt |
| GEOS, dynamically loaded by Shapely | LGPL-2.1 | https://libgeos.org/usage/download/ |
| Blender | GPL | https://www.blender.org/about/license/ |

The **Install Shapely (Internet)** operator downloads a binary wheel from PyPI
and preserves its license files under `.roof-deps/cpNNN`.

Redistribution must satisfy each dependency's license, including preservation
of notices and LGPL source obligations when distributing GEOS binaries.
