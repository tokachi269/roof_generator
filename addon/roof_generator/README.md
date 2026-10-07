# Roof Generator

Install the ZIP as a Blender 4.3+ addon, enable **Roof Generator**, and open
View3D → Sidebar → **Roof**. Select a filled planar footprint in Object Mode,
choose Flat/Gable/Hip/Shed, pitch and eave offset, then press **Generate roof**.

The result is one editable roof surface with a UV layer, material and
crease/part attributes. The surface has a perimeter boundary; walls and roof
thickness are separate modeling tasks. Source visibility is configurable,
and conversion supports Undo.

Before roof calculation, consecutive footprint edges with a turn of at most
five degrees are merged by removing the intermediate vertex (interior angles
175–185 degrees). This approximates the roof outline while preserving the
original source mesh and the provenance of all merged edges. Right-angle
corners remain.

## Base meshes (Geometry Nodes)

View3D → Sidebar → **Building** → **Create Base Meshes** creates a batch of
independent building bases. Set Count and starting dimensions in the dialog;
each object has its own Seed and shares the **Building Base · 1m** node group.
Edit the Geometry Nodes modifier inputs for live changes: Width, Depth, Max Cut,
Step Length, Minimum Span, Seed and Height. Max Cut = 0 gives the original rectangle.

The mesh consists of 1m square faces (1 Blender unit = 1m, object scale = 1).
Random side steps and whole end rows are removed from the exterior. A central
band remains, so every result is connected with one boundary and no holes.
This intentionally restricts shapes to row intervals sharing that band.
Apply the modifier when ordinary editable mesh data is needed. It is a generic
base for roofs, walls or other generators; with Roof OFF it needs no Shapely or pip.
Height = 0 retains the planar mesh. A positive Height extrudes connected walls
and closes the bottom, producing a manifold solid. Fractional heights are
supported. The **Roof Base** geometry output provides only the planar top at
that height. Enable **Roof**, choose **Roof Type** (Flat/Gable/Hip/Shed) and
**Roof Pitch** to use the existing roof generator's partition, ridge and valley
rules. Positive Height produces a closed roof/wall/bottom envelope; zero Height
exports the roof surface. **Roof Surface** exposes just the roof faces.

Roof ON requires Shapely and the enabled addon for live dimension, Seed, type
and pitch updates. The addon samples Roof Base and runs the existing Python
roof calculation; its performance and unsupported cases are unchanged.
Height and Roof toggles use the cached geometry natively without recomputation.
Changed inputs hide the stale roof until generation completes, while keeping
the current native base and walls visible. Existing v3 saved groups receive
this link repair when the addon is enabled or the file is opened. Unsupported
requests display an error in the Building panel. Use **Retry Roof** after
resolving dependency errors; no approximate roof is substituted.
The node group is also marked as an asset for reuse.

## Roof dependencies

NumPy is provided by Blender. To set up Shapely, open addon preferences and
press **Install Shapely (Internet)**. This downloads a wheel matching Blender's
CPython and installs it locally with its license files. Host Python with pip
is required; set its executable in preferences if automatic detection fails.
Automatic detection checks that each candidate can run pip, skipping unusable
launchers such as Windows app execution aliases. An explicitly selected executable
must pass the same check; failures report the selected path and pip error.

## License

This addon is **GPL-3.0-or-later**. Commercial use is permitted under the GPL;
distribution must satisfy its license and corresponding-source requirements.
See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Repository documentation: [English](https://github.com/tokachi269/roof_generator/blob/main/README.md)
| [日本語](https://github.com/tokachi269/roof_generator/blob/main/README.ja.md).
