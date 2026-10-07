# Third-party notices

Roof Generator addon source: copyright tokachi269, 2026;
GNU GPL version 3 or later. The complete text is in `LICENSE`.

Runtime dependencies are not vendored in the portable ZIP:

- NumPy: BSD-3-Clause, provided with Blender. https://numpy.org/doc/stable/license.html
- Shapely 2.1.2: BSD-3-Clause. https://github.com/shapely/shapely/blob/2.1.2/LICENSE.txt
- GEOS, dynamically loaded by the installed Shapely wheel: LGPL-2.1.
  https://libgeos.org/usage/download/ and https://libgeos.org/
- Blender: GPL; https://www.blender.org/about/license/

The explicit dependency-install operator downloads the matching binary wheel
from PyPI and retains its dist-info/license files under `.roof-deps/cpNNN`.
It does not run on addon registration. Redistributors who bundle wheels must
also satisfy those dependency licenses and the relevant source obligations.

Research papers and SGA21 source are citations in the repository's design notes;
SGA21 code, datasets and its noncommercial research port are not in this ZIP.
