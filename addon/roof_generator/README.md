# Roof Generator

Install the ZIP as a Blender 4.3+ addon, enable **Roof Generator**, and open
View3D → Sidebar → **Roof**. Select a filled planar footprint in Object Mode,
choose Flat/Gable/Hip/Shed, pitch and eave offset, then press **Generate roof**.

The result is one editable roof surface with a UV layer, material and
crease/part attributes. The surface has a perimeter boundary; walls and roof
thickness are separate modeling tasks. Source visibility is configurable,
and conversion supports Undo.

## Dependencies

NumPy is provided by Blender. To set up Shapely, open addon preferences and
press **Install Shapely (Internet)**. This downloads a wheel matching Blender's
CPython and installs it locally with its license files. Host Python with pip
is required; set its executable in preferences if automatic detection fails.

## License

This addon is **GPL-3.0-or-later**. Commercial use is permitted under the GPL;
distribution must satisfy its license and corresponding-source requirements.
See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Repository documentation: [English](https://github.com/tokachi269/roof_generator/blob/main/README.md)
| [日本語](https://github.com/tokachi269/roof_generator/blob/main/README.ja.md).
