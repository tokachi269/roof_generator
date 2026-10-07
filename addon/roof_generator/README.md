# Roof Generator

Install this folder as a Blender 4.3+ addon (or install the ZIP), enable it,
and open View3D → Sidebar → Roof. Select a filled planar footprint in Object Mode,
choose Flat/Gable/Hip/Shed, pitch and eave offset, then press Generate roof.
The result is one editable roof surface with UV layer, material and crease/part
attributes. A footprint perimeter boundary is intentional; no walls/underside
are included. Source hiding is optional; conversion is undoable.

If Shapely is missing, open addon preferences and press Install Shapely (Internet).
This requires host Python with pip; choose its executable if auto-detection fails.
No network installation runs automatically. The wheel matches Blender's CPython
and is installed locally with its license files. Source/Binary dependencies are
not bundled in the portable ZIP. See THIRD_PARTY_NOTICES.md.

This addon is GPL-3.0-or-later (see LICENSE) and contains no SGA21 optimizer,
source data or historical utility modules. It uses an independently written
parametric plane-envelope core. Geometry Nodes live generation is not provided;
the supported UI is the explicit conversion button.
