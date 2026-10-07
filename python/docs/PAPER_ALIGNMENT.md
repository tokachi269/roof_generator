# Paper Alignment Guide

This document fixes the implementation boundary for the Python and Blender port.

## Final roof generator

The footprint generator described in
[ROOF_GENERATOR_DESIGN.md](ROOF_GENERATOR_DESIGN.md) implements a plane-envelope
method. `roof_geometry`, `roof_parts`, `roof_planes`, `roof_connections` and
`roof_features` decide topology; `roof_mesh` exports that topology; mandatory
`roof_validation` observes invariants. The generated surfaces are planar.

The Blender mesh CLI selects this method with `--roof-kind`; its default
requires an authored primal graph or explicit edge roles.
`legacy_cell_preview` provides cell-based research comparisons.
The boundaries below apply to the SGA21 optimizer and role/preview APIs.
The final generator resides in the GPL addon; the SGA21-derived port is licensed
under CC BY-NC 4.0 for noncommercial use. See [license scope](../../LICENSING.md).

## Verified Sources of Truth
- Paper-facing optimization input: a roof graph.
- MATLAB roof-graph classification and topology terms: [utils/RoofGraph.m](https://github.com/llorz/SGA21_roofOptimization/blob/e9bc3264b787a6cff41a6ed92e39a3e49f3a6e11/RoofOptimization/utils/RoofGraph.m).
- MATLAB optimization entry point and energy: [fig16_recon/reconstruct_3D_roof.m](https://github.com/llorz/SGA21_roofOptimization/blob/e9bc3264b787a6cff41a6ed92e39a3e49f3a6e11/RoofOptimization/fig16_recon/reconstruct_3D_roof.m).
- Project README statement that the method uses a roof graph to encode topology: [upstream README](https://github.com/llorz/SGA21_roofOptimization/blob/e9bc3264b787a6cff41a6ed92e39a3e49f3a6e11/RoofOptimization/README.md).

## Current MATLAB To Python Mapping
- Roof graph file input
	- MATLAB source: dataset and optimization flows consume explicit roof graph files.
	- Python port: [core/roof_graph_io.py](../core/roof_graph_io.py).
- Roof graph topology classification
	- MATLAB source: [utils/RoofGraph.m](https://github.com/llorz/SGA21_roofOptimization/blob/e9bc3264b787a6cff41a6ed92e39a3e49f3a6e11/RoofOptimization/utils/RoofGraph.m).
	- Python port: [core/roof_topology.py](../core/roof_topology.py).
- Initial embedding construction and roof-vertex selection
	- MATLAB source: roof graph classification plus the initialization pattern used before [fig16_recon/reconstruct_3D_roof.m](https://github.com/llorz/SGA21_roofOptimization/blob/e9bc3264b787a6cff41a6ed92e39a3e49f3a6e11/RoofOptimization/fig16_recon/reconstruct_3D_roof.m).
	- Python port: [core/roof_pipeline.py](../core/roof_pipeline.py).
- Planarity objective and variable update
	- MATLAB source: [fig16_recon/reconstruct_3D_roof.m](https://github.com/llorz/SGA21_roofOptimization/blob/e9bc3264b787a6cff41a6ed92e39a3e49f3a6e11/RoofOptimization/fig16_recon/reconstruct_3D_roof.m).
	- Python port: [core/roof_core.py](../core/roof_core.py).
- End-to-end primal roof optimization wrapper
	- MATLAB source: [fig16_recon/reconstruct_3D_roof.m](https://github.com/llorz/SGA21_roofOptimization/blob/e9bc3264b787a6cff41a6ed92e39a3e49f3a6e11/RoofOptimization/fig16_recon/reconstruct_3D_roof.m).
	- Python port: [core/roof_runner.py](../core/roof_runner.py).

## RoofGraph.m Method Status
- Already mirrored in Python core
	- Edge extraction and face-edge conversion.
	- Outline / roof / ridge classification.
	- Neighboring face lookup for an edge.
	- Outline-edge lookup in a face.
	- Face adjacency by shared edges.
	- Ridge-neighbor lookup for a roof vertex.
	- Outline contour construction.
- Present in MATLAB but not yet ported into the Python core
	- `return_edge_ID`
	- `compute_edge_direction`
	- `compute_edge_length`
	- `find_vtx_neighboring_edges`
	- `return_ridge_edgesID_in_face`
	- `return_roof_vtxID_in_face`
	- `find_neighboring_faces_of_input_face`
	- `is_two_edge_adjacent`
	- `find_outline_edge_in_face` as a single-edge convenience API
	- `find_ovtx_neighboring_oedges`
	- `find_rvtx_neighboring_redges`
	- `find_face_without_outline_edge`
	- `find_face_with_multiple_outline_edge`
	- `check_if_two_edges_adjacent`
	- `is_graph_simple`
	- `find_neighboring_outline_vertex`
	- `find_vtx_neighboring_faces`
	- `find_vtx_neighboring_vtxs`
	- `return_edge_edit_type`
	- plotting helpers
- Porting rule for the unported list
	- Do not port these helpers just for convenience.
	- Port one only when a paper-backed Python feature or a verified MATLAB workflow actually depends on it.
	- When porting one, add its MATLAB anchor and a focused test in the same change.

## Current Non-Core Python Scope
- [blender_adapter.py](../blender_adapter.py) is restricted to projection, validation, result packaging, and routing into explicitly requested pre-SGA21 topology generation for the narrow validated single-primitive edge-role cases and the preview-only residual cases (orthogonal flat decomposition and cell-based orthogonal gable generation).
- [blender_generate_roof_from_mesh.py](../blender_generate_roof_from_mesh.py) and [blender_run_active_roof.py](../blender_run_active_roof.py) are Blender entry scripts, not paper topology generators.
- Output mesh attributes such as `roof_role_i`, `roof_height`, `roof_group_i`, and `roof_region_i` are derived Blender-side convenience data for downstream tooling, not paper-native optimization semantics.
- [core/roof_topology_generator.py](../core/roof_topology_generator.py) is kept solver-agnostic; the current SGA21-specific binding lives in [core/roof_topology_adapter.py](../core/roof_topology_adapter.py).

## Verified Default Optimization Setup
- MATLAB default path reference: [utils/construct_3D_roof_from_roof_graph.m](https://github.com/llorz/SGA21_roofOptimization/blob/e9bc3264b787a6cff41a6ed92e39a3e49f3a6e11/RoofOptimization/utils/construct_3D_roof_from_roof_graph.m).
- Initial 3D embedding: outline vertices start at `z = 0`, roof vertices start at `z = roof_height`.
- Default XY free variables: roof vertices only.
- Default Z free variables: roof vertices except one fixed roof vertex.
- Default fixed roof vertex: the first roof vertex in the roof-graph ordering.
- Solver family: quasi-Newton optimization; the Python paper-aligned path uses SciPy BFGS and does not fall back to a custom optimizer.
- Python core must preserve this default unless a separate MATLAB-backed variant is introduced and documented.

## Optimizer Alignment Status
- Verified match
	- Objective structure matches the MATLAB code path: planarity energy plus `lambda * ||XY - XY_input||_F`.
	- Variable packing matches the MATLAB code path: roof-vertex XY values followed by free roof-vertex Z values.
	- Solver family is quasi-Newton in both implementations.
- Current Python approximation
	- MATLAB uses `fminunc` with `Algorithm = quasi-newton`.
	- Python uses SciPy `minimize(..., method="BFGS")` with an explicit finite-difference Jacobian.
	- MATLAB sets `OptimalityTolerance = 1e-12` and `FunctionTolerance = 1e-12`; Python currently sets `gtol = 1e-12`.
	- MATLAB sets `MaxFunctionEvaluations` to `1e4` in [utils/construct_3D_roof_from_roof_graph.m](https://github.com/llorz/SGA21_roofOptimization/blob/e9bc3264b787a6cff41a6ed92e39a3e49f3a6e11/RoofOptimization/utils/construct_3D_roof_from_roof_graph.m) and `1e6` in [fig16_recon/reconstruct_3D_roof.m](https://github.com/llorz/SGA21_roofOptimization/blob/e9bc3264b787a6cff41a6ed92e39a3e49f3a6e11/RoofOptimization/fig16_recon/reconstruct_3D_roof.m); Python currently caps BFGS with `maxiter = 10000`.
- Known non-identities that remain visible
	- SciPy's stopping message is not numerically identical to MATLAB's `fminunc` behavior.
	- Symmetric stationary inputs can report `precision loss` in SciPy even when the returned embedding does not worsen planarity.
	- These cases should be judged by the returned embedding and planarity invariants, not by assuming SciPy's `success` bit is semantically identical to MATLAB output.

## What The Python Port Is Allowed To Do
- Parse an explicit primal roof graph from `.verts/.faces` input.
- Accept a planar Blender mesh only when that mesh already encodes a primal roof graph with interior roof vertices or ridges.
- Accept an explicit boundary-edge role input on a single rectangle or oblique quad Blender outline and use a separate pre-SGA21 topology generator to construct a primal roof graph for the validated flat, gable, and shed cases.
- Provide preview-only pre-SGA21 generation for residual orthogonal outlines in an outline-derived local frame (projected-axis alignment is not required): flat via rectangle decomposition, and gable via terminal-cap detection plus a conforming cell-based primal roof graph. Coplanar quads are retained and saddle sectors are triangulated. Both are explicitly requested preview conveniences, not paper semantics; an already-planar generated graph may bypass BFGS because the paper objective is already satisfied.
- Reproduce the MATLAB optimization structure: choose roof vertices, build the optimization variables, and minimize the planarity metric plus any explicitly supported regularizer already present in the MATLAB code path.

## What The Python Port Must Not Do Without New Evidence
- Infer roof topology automatically from a boundary-only polygon.
- Map Blender-only editing flags to paper topology terms.
- Introduce new topology labels or semantic edge roles that are not verified in the paper or MATLAB implementation.
- Treat a convenience Blender entrance heuristic or a pre-SGA21 topology generator as if it were part of the paper method.

## Required Change Checklist
Before changing the Python or Blender implementation, verify all of the following.

1. Identify the MATLAB or paper source file that justifies the behavior.
2. State whether the change belongs to the roof-graph optimization core or only to visualization / file I/O.
3. If the behavior is not evidenced by the paper or MATLAB source, keep it unsupported instead of inferring it.
4. Add or update a focused test that locks the paper-aligned behavior.
5. Validate with `python -m unittest python.tests.test_roof_core`.

## Blender Workflow In Paper-Aligned Mode
- Use Blender as a viewer or as a carrier for an already-authored roof graph.
- If the user starts from a plain outline polygon, either author the roof graph first through the annotation tools or `.verts/.faces` input, or stay within the explicitly supported single-primitive `roof_role_i` path for flat, gable, or shed generation on a rectangle or oblique quad.
- A boundary-only mesh should still fail fast unless it carries that explicit, validated edge-role input.
