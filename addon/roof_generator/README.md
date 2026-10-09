# Roof Generator addon

Install the repository's `packages/roof_generator-1.4.1.zip` in Blender 4.3+.
No external Python packages are required.

The Roof sidebar conversion button creates ordinary editable meshes with UVs,
material and Cell/edge provenance. Rectangle gable/hip/shed/flat and hole-free
orthogonal compound flat surfaces have analytic mesh support. Supported compound
gable junctions and nonorthogonal convex quadrilateral primitives use the same
GeometryProblem/embedding/validated-mesh pipeline. General oblique compound
partitioning, arbitrary offset/partial/parallel junctions and compound hip/shed
remain unsupported. Unsupported conversion fails before scene
mutation. The full current capability table is in the repository README.

`core/` owns normalization, minimum partitions, architectural interpretation,
validated topology candidates, stable seeds, geometry and mesh validation.
Blender adapters only read source meshes and create output objects.

Source is GPL-3.0-or-later; see `LICENSE` and `THIRD_PARTY_NOTICES.md`.

## Native building bases

View3D sidebar > Building > Create Base Meshes creates editable Geometry Nodes
bases. Width, Depth, Seed and Height remain modifier inputs. Roof ON requests
the same canonical roof API; unsupported roofs leave the base and walls visible.
Height and Roof OFF edits reuse the already validated roof cache. Saved legacy
roof caches are invalidated when the current addon updates the building.
