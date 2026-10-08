# Roof Generator addon

Install the repository's `packages/roof_generator-1.2.0.zip` in Blender 4.3+.
No external Python packages are required.

The Roof sidebar conversion button creates ordinary editable meshes with UVs,
material and Cell/edge provenance. Rectangle gable/hip/shed/flat and hole-free
orthogonal compound flat surfaces have analytic mesh support. Supported compound
gable junctions expose a GeometryProblem through the core API; their nonlinear
mesh embedding is not implemented. Unsupported conversion fails before scene
mutation. The full current capability table is in the repository README.

`core/` owns normalization, minimum partitions, architectural interpretation,
validated topology candidates, stable seeds, geometry and mesh validation.
Blender adapters only read source meshes and create output objects.

Source is GPL-3.0-or-later; see `LICENSE` and `THIRD_PARTY_NOTICES.md`.
