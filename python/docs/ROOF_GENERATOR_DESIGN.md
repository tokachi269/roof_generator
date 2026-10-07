# Footprint → editable Blender roof

## Scope and architecture

The generator produces an editable planar roof surface from a simple footprint,
including convex quadrilaterals and concave, oblique multi-part outlines.
Roof types are flat, gable, hip and shed.

Current routes:

- Planar footprint → `addon/roof_generator/core` → RoofParts / roof-plane
  connections → validated mesh → Blender conversion operator.
- Authored primal/dual graph → `roof_pipeline` / `roof_runner` → planarity BFGS →
  `blender_adapter.MeshSpec` → `blender_import_roof_result.create_mesh_object`.
- Boundary roles → `roof_topology_generator` single rectangle/parallelogram →
  `roof_topology_adapter` → comparison meshes.
- Preset preview → orthogonal frame → coordinate-level cells → greedy rectangles
  → `build_orthogonal_gable_roof_graph` → comparison meshes. This is legacy only.

The cell preview assigns zero to eave samples and the requested height to all
other cell corners, midpoints and centers. Its internal edges are not intersections
of roof planes. Triangles can hide incompatible slopes; the topology depends on
coordinate levels, lacks a RoofPart adjacency/connection model, does not identify
valleys/hips, and cannot generalize to oblique concave or tapered quads. It is
available as a legacy research preview.

## Research and decisions

The following comparison identifies the partition, primitive and connection
choices used by the bounded plane-envelope method.

| Source | Partition / evaluation | Primitive / connection / ridge, hip, valley | Decision |
| --- | --- | --- | --- |
| [Kada & McKinley 2009](https://www.isprs.org/proceedings/xxxviii/3-w4/pub/CMRT09_47.pdf), §§2.1–2.3 | Group nearly parallel outline lines, average a selected subset, avoid small cells. | Parameterized flat/shed/gable/hip/Berliner blocks, LiDAR normal votes and parameter fitting; replace junction blocks using neighboring fits. | Adopt small parts, provenance and adjacency. Reject footprint generalization, LiDAR dependency and corner/T/cross junction classes. |
| [Laycock & Day 2003](https://www.sthu.org/misc/SKRW14/papers/LaycockDay_2003_AutomaticallyGeneratingRoofModelsBuildingFootprints.pdf), §§6–7 | Rectilinear reflex rays; grow/merge rectangles from skeleton lines. | Hip from inward skeleton and supporting-edge distance; gable changes end slopes; merges roofs. | Adopt supporting-edge planes and reflex candidates. Do not port midpoint skeleton editing or rectilinear-only partitioning. |
| [Sugihara & Hayashi 2006](https://www.jstage.jst.go.jp/article/journalac2003/15/0/15_0_67/_pdf), §3; [2007](https://www.jstage.jst.go.jp/article/journalac2003/16/0/16_0_309/_pdf), §3 | RL expression identifies reflex cuts; select branches with good aspect ratios to avoid strips and excessive subdivision. | Rectangular roof solids, Boolean assembly; narrower roofs extend toward wider roofs. | Adopt reflex cuts and explicit aspect objective. Reject RL shape cases, right-angle rectification and rectangle-only primitives. |
| [Kelly & Wonka 2011](https://www.peterwonka.net/Publications/pdfs/2011.TOG.Kelly.ProceduralExtrusions.TechreportVersion.final.pdf), §4 | Input plan plus per-edge profiles, rather than optimizing a quad partition. | Sweep direction planes; events change active-plan topology; halfedges assemble planar faces, including holes; ridge arcs arise at plane events. | Adopt plane-defined geometry and shared topology. Full event machinery for negative offsets, dormers and profiles is beyond the four requested roof types. |
| [twak/campskeleton](https://github.com/twak/campskeleton), [twak/siteplan](https://github.com/twak/siteplan) | Weighted skeleton / procedural plan and profile editing, not a minimal architectural-part partition solver. | Java robust event processing and direction planes; siteplan adds profile events and shell editing. | Apache-2.0. JVM/Maven and Java GUI/runtime requirements complicate Blender packaging, including Windows. |
| [CGAL skeleton](https://doc.cgal.org/latest/Straight_skeleton_2/index.html), [partition](https://doc.cgal.org/latest/Partition_2/index.html) | Optimal convex partition or approximation (not constrained to architectural quads); inward edge events / positive weights. | Skeleton regions belong to source edges; event arcs lift onto roof planes. | Strong optional future backend. Full concave skeleton is not equivalent to a global minimum of infinite edge planes. Avoid silently approximating it that way. C++ bindings, ABI/builds and GPL/commercial package licensing need separate distribution work. |

GEOS/Shapely is used for polygon split, overlay, union, noding and constrained
triangulation. Shapely 2.1.2 has BSD licensing; its GEOS wheel libraries are LGPL
and dynamically loaded. Windows x64 and Linux wheels are available for the
supported CPython versions. `requirements-roof.txt` pins Shapely 2.1.2.
The addon preferences and `install_roof_dependencies.py` use host Python with pip
to install a wheel matching Blender's CPython under `.roof-deps/cpNNN`.
GEOS handles polygon robustness; the generator implements bounded architectural
selection and affine plane clipping.

## Geometry and RoofPart

Normalize a single simple loop: finite coordinates, positive area, CCW winding,
remove only tolerance-collinear vertices, preserve the source-edge mapping.
Reject holes, touching/self-crossing outlines, degenerate edges and nonplanar
Blender input. Use an intrinsic edge frame to avoid world-axis dependence and
large-coordinate cancellation; tolerance snap must never rectify the building.

`RoofPart` contains id, footprint polygon, source footprint edge segments,
neighbors, roof type, ridge/eave pair or explicit plane definitions, eave height,
pitch (rise/run), and provenance (cuts and parameter origin). Geometric queries
expose convexity, parallel opposite pairs, one parallel pair, approximate
orthogonality and aspect ratio. There is no catch-all RESIDUAL primitive.

## Decomposition and adjacency

At reflex vertices generate cuts from the original edge directions (both signs)
and visible vertex diagonals. Shoot to the first boundary intersection and require
an interior segment. Recursively enumerate valid splits until parts are convex
triangles/quadrilaterals; gable requires quads, while flat/hip can use triangles.
Select complete partitions lexicographically by:

1. part count;
2. worst aspect ratios, descending (minimum-area bounding rectangle);
3. total cut length;
4. cut direction deviation from original edge directions;
5. stable intrinsic-coordinate cut/part signatures.

No weighted sum. The optimum is among enumerated candidates, not a claim of the
global minimum over every possible Steiner partition. Bound search complexity and
raise unsupported if the bound is exhausted; do not fall back to greedy cells.
Validate area coverage and disjoint interiors. Adjacency is positive-length shared
boundary, including partial boundary overlaps, never a guessed nearest neighbor.

## Parametric roofs and connectors

For a CCW edge, signed inward distance is affine. Hip uses all inward eave
planes `z = eave + pitch * distance`. The local roof is their lower envelope;
this exactly models a convex part's equal-pitch hip. Gable uses a selected pair of
opposite eave edges and their lower envelope, clipped by the part: the ridge is
their plane-plane intersection. Nonparallel eaves allow an inclined ridge, keeping
both faces planar on a general quad. Shed is one inward slope plane; flat is one
constant plane. End support lines define extent, not extra guessed vertices.

Cuts are construction boundaries, not automatically eaves. Each neighboring part
can complete its roof support across a cut. Remove cut-only vertical support
constraints. Propagate neighboring exterior eave planes that do not separate the
source part (their nonnegative halfplane contains it). This bounds extensions at
physical eaves and lets a narrower roof terminate against the host's slope.
Propagation through adjacency is to a fixed point. Keep partial exterior support
edges; extensions are always clipped to the original building polygon.

Compute each part's plane patches by affine inequalities. On overlapping domains,
the exposed roof is the upper envelope of these lower-envelope solids, the roof
analogue of a Boolean union. Remove concealed patches with polygon overlay using
plane-plane equal-height lines. This produces valleys between crossing parts and
hips/ridges within a part, without L/T/U generators. Coplanar patches are merged.
Validate height continuity along every interior boundary. Incompatible requested
height offsets, isolated vertical steps or connector configurations fail explicitly;
we do not invent flashing/wall geometry or output an open broken surface.

This is a documented roof interpretation, not recovery of an unknown real roof
from footprint alone. Explicit part parameters permit other pitch/orientation
choices. Reject connector arrangements that cannot produce a continuous surface.

## Topology, mesh and optimization data flow

`Blender planar mesh → plane frame / boundary → normalized footprint → partition
→ RoofParts / adjacency → local plane patches → connected exposed patches
→ RoofTopology (planar regions, loops, shared features) → mesh tessellation
→ validated MeshSpec → one Blender mesh object`.

Topology precedes triangulation. Ordinary simple planar regions become n-gons;
regions with holes are tessellated separately using GEOS constrained Delaunay.
`roof_features` classifies the connected region boundaries before tessellation.
Node all resulting export boundaries and insert shared edge vertices before indexing.
Weld only within numerical tolerance, reject unequal heights, classify shared
crease edges by the adjacent planes (convex horizontal ridge / sloped hip;
concave valley). Coplanar tessellation edges are not roof features. No debug lines,
parts, caps or hidden faces are inserted into the final surface.

A roof surface is a two-manifold **with one intentional perimeter boundary**.
It is not a closed volume: no underside/building walls are requested. Validation
requires exactly one perimeter matching the footprint and two oppositely directed
incidences per internal edge. This distinguishes intended eaves/gable ends from
holes or nonmanifold junctions.

The research optimizer optimizes the embedding of an authored roof graph. The footprint
generator creates planar faces directly. An optimization
adapter can consume the determined graph, but may not choose topology or repair
an invalid connector. The cell preview is a legacy research tool.

## Acceptance validation

Named final-mesh fixtures cover all 16 acceptance scenarios: rectangle gable,
hip, shed; rotated rectangle; parallelogram; trapezoid; general convex quad; L,
T, U; rotated L; oblique L/T; unequal-width join; terminating ridge; valley;
residential multiple-reflex outline. Dimensions include residential wings.
Flat and explicit part overrides also have coverage.

Each fixture validates indices, nonzero face areas, no duplicate faces/vertices,
planarity, oriented edge/vertex manifoldness, no T-junctions, polygon projection
coverage/overlap, a single perimeter, deterministic output, translation/rotation
invariance, and equivalence after adding redundant collinear boundary vertices.
Checks cover expected part counts and geometric ridge/hip/valley presence as well as
mesh metrics. Negative cases must raise unsupported without emitting a mesh.

The 79 optimizer/legacy tests cover the research path. Blender smoke calls the
source-object entry, creates and validates the final meshes, unwraps UVs and
assigns materials. It exercises object transforms and gridded sources, saves a
reviewable .blend, and renders representative L/T/U/oblique views for inspection.

## Implemented numerical and deployment boundaries

Intrinsic coordinates are divided by perimeter. Input/overlay arithmetic uses a
`1e-11` precision grid; the final region overlay uses a common `2e-9` grid to
collapse sub-tolerance slits before indexing. Vertex sharing uses four times that
tolerance; mandatory validation bounds residuals at twenty times it. These are
numerical precision allowances, not architectural scoring weights. Face heights
come from incident roof planes; inconsistent heights fail validation. Straight
degree-two export waypoints are removed only when all incident faces agree.

The final Blender entry hides, but retains, the input footprint after successful
import, including in renders. It makes no topology repairs. The standard mesh
CLI delegates only for explicit `--roof-kind`; the paper-aligned default is
available. Windows x64 wheels support CPython 3.10–3.13.
Blender execution is validated on Linux with Blender 4.3.2; CI covers the core and addon
distribution on Windows/Linux with Python 3.11/3.13.

The representative smoke renders include separately derived facade objects for
context. Facades and render lights never enter the final roof mesh.

Final source-object transforms are multiplied in double precision using the
existing evaluated mesh read view; output vertex coordinates are stored relative
to the source world translation, not as large float32 world coordinates. Smoke
also exercises a rotated footprint translated by one million units. Generation
requires Object Mode, so no incomplete Edit Mode geometry/state is silently used.

## Validated delivery

The validation suite contains 90 tests, including 79 optimizer/legacy tests.
Blender 4.3.2 generates, validates and UV-unwraps all 16
mandatory fixture meshes; transform, million-unit translation, gridded source
and CLI checks pass. Invalid nonplanar input leaves the scene
unchanged. Six rendered scenes cover L, T, U, oblique L,
general quad and the residential four-part footprint.

| Fixture | Parts | Final vertices | Final faces | Interior features |
| --- | ---: | ---: | ---: | --- |
| rectangle_gable | 1 | 6 | 2 | ridge: 1 |
| rectangle_hip | 1 | 6 | 4 | ridge: 1, hip: 4 |
| rectangle_shed | 1 | 4 | 1 | none (single plane) |
| rotated_rectangle | 1 | 6 | 2 | ridge: 1 |
| parallelogram | 1 | 6 | 2 | ridge: 1 |
| trapezoid | 1 | 6 | 2 | ridge: 1 |
| general_convex_quad | 1 | 6 | 2 | ridge: 1 |
| orthogonal_L | 2 | 10 | 4 | ridge: 2, hip: 2, valley: 1 |
| orthogonal_T | 2 | 12 | 4 | ridge: 2, valley: 2 |
| orthogonal_U | 3 | 14 | 6 | ridge: 3, hip: 4, valley: 2 |
| rotated_L | 2 | 10 | 4 | ridge: 2, hip: 2, valley: 1 |
| oblique_L | 2 | 10 | 4 | ridge: 2, hip: 2, valley: 1 |
| unequal_width_join | 2 | 12 | 4 | ridge: 2, valley: 2 |
| terminating_ridge | 2 | 12 | 4 | ridge: 2, valley: 2 |
| valley_join | 2 | 10 | 4 | ridge: 2, hip: 2, valley: 1 |
| residential_multi_reflex | 4 | 20 | 8 | ridge: 4, hip: 4, valley: 4 |

Maximum measured float32 Blender face planarity error: `1.83e-07` world
units (smoke limit `2e-5`). Saved outputs are reproducible generated artifacts
under ignored `python/out/acceptance`, not fixture-specific production
geometry. `all_roofs.blend` holds the ordinary editable meshes; individual
representative scenes add separate walls/lights for visual review.

## Standalone addon delivery

The final-generation modules reside under `addon/roof_generator/core/`.
The addon uses metric mesh projection and a Blender output importer. Registration is
lazy so importing the geometry library outside Blender remains possible.
The sidebar conversion operator exposes type/pitch/eave offset, colors and source
visibility. Conversion is explicit and undoable, with no automatic handlers.
The ZIP installer smoke exercises the actual registered operator on all 16
fixtures, UV/material editability, transforms, failure without scene mutation,
and disable/re-enable lifecycle.

Optimizer/legacy graph-input tests use the synthetic residential hip graph in
`python/tests/fixtures/authored_hip/`. Source and research references are in
`reference/README.md` and the paper alignment guide. Component licenses and
conditions are defined in `LICENSING.md`.
