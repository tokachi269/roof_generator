# Graph-first evaluation: rectangle and terminal attachment

## Result and boundary

The new path selects primitive face incidence and ridge/hip/valley meanings
**before** solving roof geometry. It contains no roof planes, polygon overlay,
wavefront or Boolean. Rectangles reach validated ordinary meshes. Orthogonal
single-reflex footprints reach a two-cell composed RoofGraph and an explicit
geometry problem; **there is no nonlinear L geometry solver or final L mesh
generator in this evaluation**. Unsupported requests raise `UnsupportedGraphError`
without substituting the reference roof.

Starting SHA: `1de443f53740a5a71e5512f421b691d0e7a256f5`.
Measured implementation SHA: `1c58a9683e54f4e51e3b133516964f7be1b37b1e`, clean tree.
Subsequent evaluation commits contain documentation/evidence only. The final
commit is available in Git history and the task report.

The production addon, ZIP, pre-existing tests/fixtures, semantic baseline,
semantic harness and performance harness are byte-identical to the starting
commit. The existing CI gates remain; one independent rectangle Blender step
was added. The new path is a development API under `python/graph_first/`, not
an addon UI switch or a replacement production generator.

## Contract and processing

`RoofGraph` is immutable and stores:

- Ordered normalized outline and original exterior-edge IDs.
- `Vertex(seed, role, boundary, cells)`: disposable XY, corner/ridge-end/junction
  role, fixed boundary edge/t location when applicable, incident source cells.
- `Face(loop, cells, eaves)`: vertex-index cycle, originating primitive and
  physical eave IDs. No plane or independently inferred mesh semantics.
- `Edge(vertices, faces, kind, boundary)`: shared vertex IDs, incident face IDs,
  declared ridge/hip/valley/eave/gable-end meaning and exterior interval provenance.
- Roof type; face adjacency is derived from edge incidence.

Construction validates directed incidence, disk Euler characteristic, one
boundary loop, connected faces, manifold vertex links, complete exterior interval
ownership and valid/unique indices. It is a manifold surface **with boundary**,
not a closed building solid. Coordinates are not used to rediscover edge meaning.
Mesh export keeps this exact graph and rejects invalid projection, moved fixed
boundary, coincident vertices, zero/negative faces, nonplanarity or bad normals.

The sequence is:

1. Scalar finite/simple-polygon validation, removal of redundant collinear points
   with provenance, CCW/cyclic normalization and a rigid intrinsic frame scaled
   by perimeter. Detect edge directions, parallel pairs and reflex vertices.
   No orthogonal snapping.
2. Partition ordered boundary arcs using reflex incident-edge extensions.
   Output rectangular corner IDs, noded boundaries, exterior/artificial intervals
   and the shared cell interval. No roof is generated while selecting a partition.
3. Make indexed rectangle primitive cycles, select physical eaves and declare
   primitive edge meanings. Match a complete branch gable side to a terminal
   partial host eave side. Graft cycles and remove the artificial separator.
4. Initialize already-chosen connectivity in 2D along declared ridge directions,
   guarding against crossings/outside spokes. Export the fixed-incidence geometry
   problem; solve rectangles analytically.
5. Export coordinates against that same graph; the mesh has no second semantic
   decision layer. Debug cells/cuts are not mesh faces.

### Decomposition algorithm

For one reflex vertex there are two incident-edge extensions to the first visible
boundary hit. Following the two boundary arcs gives the two candidate partitions.
Discard candidates that are not two rectangles. Choose lexicographically by
sorted worst aspect ratios, cut length, then stable intrinsic chord signature.
Two rectangles are the minimum for this scoped input because one rectangle
cannot contain a reflex vertex. This is **not** a general minimum rectangular
partition implementation. There is no recursive search tree, grid rasterization,
roof-candidate evaluation or Shapely split.

For the L input below the candidates cut horizontally or vertically at the
reflex corner. The selected cell 0 is `[5.2,14.2] × [0,5.6]` and cell 1 is
`[0,5.2] × [0,12.8]`. Their single shared interval is
`(5.2,0) → (5.2,5.6)`. An independently authored alternate partition produces
identical roof incidence; its originating cell IDs need not be identical.

### Terminal graft semantics

The shared interval must be the entire branch gable side and a partial host
physical eave side touching exactly one host corner. Ridge axes must be
perpendicular and an exterior eave must continue across the removed chord hit.
These adjacency/primitive relations select the operation; no fixture name is
visible to the core and there is no L-specific shape class.

Terminate each primitive's near ridge port at the connection. The two surviving
ridge ports, the continued convex exterior corner and the shared reflex endpoint
form ridge/ridge/hip/valley spokes. With equal transverse widths there is one
four-valent junction. Under common pitch/eave assumptions, unequal widths split
it into two three-valent junctions: wider ridge plus convex hip at one, narrower
ridge plus reflex valley at the other; join the junctions with a hip.
Width ordering, not roof-plane intersections or final heights, decides this
refinement. Equality is a real topology transition.

Laplacian XY is only an initializer. Both unconstrained and axis-constrained
harmonic drawings can cross a concave boundary. The initializer now checks the
scalar drawing and, if necessary, backtracks junction coordinates along the
same axes towards their common intersection. The coincident limit is never
emitted; failure is explicit. This is a metric initialization adjustment after
incidence selection, not a different roof or a geometry-derived topology.

## Inspectable examples

The [rectangle JSON](graph-first/rectangle_gable.json),
[rectangle drawing](graph-first/rectangle_gable.svg),
[L JSON](graph-first/orthogonal_L.json) and
[L drawing](graph-first/orthogonal_L.svg) contain actual exported output from the
measured commit. SVG positions are initial XY, not solved L roof coordinates.

For a `12.8 × 7.2` gable rectangle, vertices 0–3 are exterior corners, 4–5 are
fixed gable ridge ports `(12.8,3.6)` and `(0,3.6)`. Faces are
`(3,0,4,5)` and `(4,1,2,5)`, with one shared ridge `(4,5)` and complete
exterior ownership. Pitch 0.5 gives ridge height 1.8 above the eave. The hip
rectangle has four faces, one ridge and four hips; flat/shed each have one face.
Square hip has one apex and no zero-length ridge.

For the L outline
`(0,0),(14.2,0),(14.2,5.6),(5.2,5.6),(5.2,12.8),(0,12.8)`:

| Item | Actual graph |
| --- | --- |
| Cells / shared intervals | 2 / 1 |
| Vertices / edges / faces | 10 / 13 / 4 |
| Ridge edges | `(6,9)`, `(7,8)` |
| Hip edges | `(2,8)`, `(8,9)` |
| Valley edge | `(5,9)` from the reflex corner |
| Junctions | 8 and 9, degree 3, both incident to both cells |
| Face cycles | `(4,5,9,8,7)`, `(8,2,3,7)`, `(5,0,6,9)`, `(6,1,2,8,9)` |
| Face adjacency | `(1,3)`, `(0,2)`, `(2,3)`, `(0,1)`, `(0,3)` |
| Perimeter ownership | All six original edges, each interval once |

Here graph vertex 2 is `(0,0)`, 5 is the reflex `(5.2,5.6)`, and surviving
ridge ports 6 and 7 are `(2.6,12.8)` and `(14.2,2.8)`. Current initializer
junction XY is `(5.6,2.8)` and `(2.6,7.0667)`; these positions are deliberately
not advertised as final roof geometry.

## SGA21 boundary and reuse

Historical `a0c8b36` modules and paper-alignment notes were inspected before
implementation. The useful contract is variable XY/Z IDs, initial/reference
coordinates and fixed face cycles. Its planarity objective is the sum of the
smallest sample-covariance eigenvalue of each face; the historical implementation
used finite-difference BFGS and optional XY displacement regularization.
The dual graph-to-primal incidence and Laplacian initialization also informed
this separation. No historical module was restored or imported.

`GeometryProblem` exports `initial_vertices`, `faces`, `variable_xy`,
`variable_z`, `fixed_z` and `ridge_directions`. The L example has variable XY
and Z at vertices `(8,9)` (six scalar unknowns), fixed footprint XY, fixed eave
Z, and nonflat cap heights 1.3 and 1.4 at common pitch 0.5. Normalized values
are divided by perimeter 54. These anchors prevent the trivial flat optimum.
The solver must preserve ridge direction and graph incidence and may never
add/remove faces or select a junction.

An independent test supplies a planar witness for this same graph: world
junctions `(2.8,2.8,1.4)` and `(2.6,3.0,1.3)`. Literal affine face equations,
not production plane/envelope helpers, verify its planarity. Export accepts this
witness and rejects the unsolved initial 3D coordinates. It proves the example
has a valid embedding, **not** that a nonlinear solver has been implemented.

## Semantic comparison and checks

Primary proof reads the graph directly: primitive face counts, edge labels,
source/eave ownership, junction degree, shared interval, disk incidence and
coverage. A deliberately changed valley label must fail the independent proof.
Rigid translation/rotation, cyclic start, winding and redundant collinear
vertices preserve the tested incidence, physical eaves and originating cells;
original-edge IDs are checked geometrically after the known transformations.
Directed shed slope requires an explicit physical low eave for the metamorphic
proof: a symmetric rectangle has no intrinsic directed slope. Symmetric gable
orientation without an explicit architectural direction remains ambiguous too.

Secondary comparison reuses the existing semantic harness unchanged:

- Rectangle gable/hip/shed/rotated gable/flat snapshots agree completely on the
  compared indexed mesh, support geometry and feature labels.
- L agrees on abstract face incidence and ridge/hip/valley labels after matching
  boundary/ridge ports. Internal XYZ and final planes are not compared.
- New `Face.cells` means originating primitive, whereas reference `face_parts`
  means geometric visible-solid contributor. They are different contracts and
  are not forced to match. The new topology remains solver-independent.

At the starting SHA the reference already uses a scalar interval-envelope in
its connector rather than the old repeated polygon-overlay connector at
`9f967642`. It still determines visible roof geometry from supports/planes before
assembling topology. Measurements below are of **current unchanged production**,
not a rerun of the earlier slow implementation. The frozen semantic baseline
from that earlier harness remains unchanged.

Validation performed:

- All 50 core tests pass, including all pre-existing acceptance/harness tests.
- Unchanged semantic CLI: all 27 snapshots agree with its committed baseline.
- Fresh isolated processes forbid Shapely and reference-generator imports while
  generating rectangle meshes and the L geometry problem.
- Additional deterministic exploration, seed 1701: 100 L proportions, widths
  3–7 and arm extensions 6–12; all accepted drawings pass independent polygon
  disjointness/coverage/edge-containment checks. The discovered long-arm failure
  is retained as a direct regression test, not only a random observation.
- Blender 4.3.2 creates all four rectangle mesh objects, validates manifold
  surface/boundary edges and positive normals, unwraps UVs, assigns materials
  and saves `rectangle_roofs.blend`. [Smoke report](graph-first/blender-rectangle.json).
  [Actual Blender render](graph-first/rectangle-roofs.png), left to right:
  gable, hip, shed, flat. Both the rectangle render and L drawing were visually inspected.
- Existing packaged addon ZIP still matches its canonical source. CI adds the
  rectangle proof to the existing Ubuntu/Windows and actual addon gates.

## Unprofiled performance

[Measurement JSON](graph-first/performance.json): Python 3.12.14, Linux x86-64,
101 recorded samples after 5 warmups, clean measured commit, no profiler, no new
cache. Final measurements ran after Blender smoke completed. Values below are
median milliseconds; stage totals are measured per call, not sums of medians.
Mesh export includes new projection/planarity validation but excludes Blender
object creation, UVs and materials.

| Case | Analysis | Cells | Graph composition | Footprint→Graph | Graph p95 | Analytic solve | Mesh export | Total core |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Rectangle gable | 0.059 | 0.058 | 0.145 | 0.271 | 0.379 | 0.016 | 0.119 | 0.417 |
| Rectangle hip | 0.060 | 0.059 | 0.160 | 0.283 | 0.328 | 0.027 | 0.227 | 0.555 |
| Rectangle shed | 0.058 | 0.058 | 0.099 | 0.216 | 0.275 | 0.015 | 0.048 | 0.282 |
| Rectangle flat | 0.058 | 0.058 | 0.098 | 0.216 | 0.283 | 0.011 | 0.048 | 0.277 |
| Orthogonal L | 0.108 | 0.234 | 0.977 | 1.327 | 1.478 | Not implemented | Not implemented | Not measured |
| Rotated L | 0.109 | 0.237 | 0.979 | 1.341 | 1.456 | Not implemented | Not implemented | Not measured |

L geometry-problem export takes 0.016 ms median, separately. SGA21 nonlinear
solve is `null` for every case; rectangle solves are explicitly analytic.

| Case | Reference through connection cold / warm | Reference complete core cold / warm |
| --- | ---: | ---: |
| Rectangle gable | 3.419 / 0.704 | 4.686 / 1.957 |
| Rectangle hip | 3.891 / 0.758 | 5.741 / 2.577 |
| Rectangle shed | 3.161 / 0.591 | 3.942 / 1.356 |
| Rectangle flat | 3.018 / 0.552 | 3.820 / 1.314 |
| Orthogonal L | 8.434 / 0.953 | 10.690 / 3.110 |
| Rotated L | 8.928 / 0.956 | 11.205 / 3.138 |

Reference stages are measured through the unchanged performance harness; cold
clears its caches for every call, warm reuses them. Reference connection already
solves plane heights, so it performs more work than new pre-solver Graph. A warm
reference is faster than the uncached new L graph on this input. These data do
not establish a general end-to-end L speedup, city throughput or performance on
14–40 distinct vertices. They demonstrate a millisecond graph construction on
this scoped terminal case without geometric candidate roofs.

## Dependencies, unresolved cases and next decision

New runtime: **zero Shapely calls/imports and zero third-party dependencies** in
`python/graph_first/`. Shapely remains in unchanged production, independent test
coverage oracles, and the test-only rectangle snapshot adapter. The performance
comparison imports production only in its comparison tool.

The L proof is sufficient to continue evaluating a middle-interval attachment
and multiple attachments as graph operations. It is not sufficient to enable
T/U production or claim a fast general building generator. Pending work:

- Multi-reflex orthogonal partitioning using a bounded known rectangle algorithm.
- Middle-interval/T attachment and interactions of multiple terminal attachments
  for U; validate cycles, branch degree and valley ownership independently.
- Reusable nonlinear solve with fixed incidence, ridge constraints, nonflat
  anchors and explicit failure; measure convergence and complete-mesh semantics.
- Explicit architectural direction where symmetric primitives are ambiguous.
- Nonorthogonal quadrilateral cells, mixed roof types/pitches/eaves, height steps,
  interior holes and nonterminal same-axis connections.
- Thousands of independent buildings and 14–40 distinct-vertex timings after
  those cases actually work; no extrapolation from rectangles/L.

This evaluation stops here, as requested. The existing production generator is
available explicitly as a comparison route; the new API never silently calls it.
