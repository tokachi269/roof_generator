# Footprint → editable Blender roof

## Scope and observed baseline

Baseline: `develop` at `eb84407b6afe8a9f394bdfbbda1993b4a166b87f`.
Before edits, `python -m unittest python.tests.test_roof_core`
passes all 79 tests. Direct generation rejects a trapezoid, a general convex
quadrilateral, and an oblique concave L outline. There is no hip primitive.

Current routes:

- Authored primal/dual graph → `roof_pipeline` / `roof_runner` → SGA21 BFGS →
  `blender_adapter.MeshSpec` → `blender_import_roof_result.create_mesh_object`.
- Boundary roles → `roof_topology_generator` single rectangle/parallelogram →
  `roof_topology_adapter` → comparison meshes. This remains compatible.
- Preset preview → orthogonal frame → coordinate-level cells → greedy rectangles
  → `build_orthogonal_gable_roof_graph` → comparison meshes. This is legacy only.

The cell preview assigns zero to eave samples and the requested height to all
other cell corners, midpoints and centers. Its internal edges are not intersections
of roof planes. Triangles can hide incompatible slopes; the topology depends on
coordinate levels, lacks a RoofPart adjacency/connection model, does not identify
valleys/hips, and cannot generalize to oblique concave or tapered quads. It is
isolated for regression, never used by the final generator.

## Research and decisions

Primary papers were read, including their algorithm sections (not just abstracts).
The following are concise comparisons; the implementation below is our bounded
plane-envelope method, not a claim to reproduce these papers.

| Source | Partition / evaluation | Primitive / connection / ridge, hip, valley | Decision |
| --- | --- | --- | --- |
| [Kada & McKinley 2009](https://www.isprs.org/proceedings/xxxviii/3-w4/pub/CMRT09_47.pdf), §§2.1–2.3 | Group nearly parallel outline lines, average a selected subset, avoid small cells. | Parameterized flat/shed/gable/hip/Berliner blocks, LiDAR normal votes and parameter fitting; replace junction blocks using neighboring fits. | Adopt small parts, provenance and adjacency. Reject footprint generalization, LiDAR dependency and corner/T/cross junction classes. |
| [Laycock & Day 2003](https://www.sthu.org/misc/SKRW14/papers/LaycockDay_2003_AutomaticallyGeneratingRoofModelsBuildingFootprints.pdf), §§6–7 | Rectilinear reflex rays; grow/merge rectangles from skeleton lines. | Hip from inward skeleton and supporting-edge distance; gable changes end slopes; merges roofs. | Adopt supporting-edge planes and reflex candidates. Do not port midpoint skeleton editing or rectilinear-only partitioning. |
| [Sugihara & Hayashi 2006](https://www.jstage.jst.go.jp/article/journalac2003/15/0/15_0_67/_pdf), §3; [2007](https://www.jstage.jst.go.jp/article/journalac2003/16/0/16_0_309/_pdf), §3 | RL expression identifies reflex cuts; select branches with good aspect ratios to avoid strips and excessive subdivision. | Rectangular roof solids, Boolean assembly; narrower roofs extend toward wider roofs. | Adopt reflex cuts and explicit aspect objective. Reject RL shape cases, right-angle rectification and rectangle-only primitives. |
| [Kelly & Wonka 2011](https://www.peterwonka.net/Publications/pdfs/2011.TOG.Kelly.ProceduralExtrusions.TechreportVersion.final.pdf), §4 | Input plan plus per-edge profiles, rather than optimizing a quad partition. | Sweep direction planes; events change active-plan topology; halfedges assemble planar faces, including holes; ridge arcs arise at plane events. | Adopt plane-defined geometry and shared topology. Full event machinery for negative offsets, dormers and profiles is beyond the four requested roof types. |
| [twak/campskeleton](https://github.com/twak/campskeleton), [twak/siteplan](https://github.com/twak/siteplan) | Weighted skeleton / procedural plan and profile editing, not a minimal architectural-part partition solver. | Java robust event processing and direction planes; siteplan adds profile events and shell editing. | Checked source repositories, README and licenses: Apache-2.0. JVM/Maven and Java GUI/runtime complicate Blender packaging, including Windows. No runtime dependency here. |
| [CGAL skeleton](https://doc.cgal.org/latest/Straight_skeleton_2/index.html), [partition](https://doc.cgal.org/latest/Partition_2/index.html) | Optimal convex partition or approximation (not constrained to architectural quads); inward edge events / positive weights. | Skeleton regions belong to source edges; event arcs lift onto roof planes. | Strong optional future backend. Full concave skeleton is not equivalent to a global minimum of infinite edge planes. Avoid silently approximating it that way. C++ bindings, ABI/builds and GPL/commercial package licensing need separate distribution work. |

GEOS/Shapely is used for polygon split, overlay, union, noding and constrained
triangulation. Shapely 2.1.2 has BSD licensing; its GEOS wheel libraries are LGPL
and dynamically loaded. Windows x64 and Linux wheels are available for the
supported CPython versions. Install using the Python bundled with Blender, not a
random system Python. Pin the version in `requirements-roof.txt`; `install_roof_dependencies.py`
queries the local Blender CPython and installs a matching wheel in ignored
`.roof-deps/cpNNN`, without requiring pip inside Blender. Ship this installer and
requirements rather than platform binaries in the source repository. No JVM or CGAL compilation is needed. Missing dependency raises a
clear installation error. GEOS remains responsible for polygon robustness; we
implement only the bounded architectural selection and affine plane clipping.

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

## Topology, mesh and SGA21 data flow

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

The SGA21 objective and authored graph path remain unchanged. The new generator
already creates planar faces and does not run BFGS by default. An optimization
adapter can consume the determined graph, but may not choose topology or repair
an invalid connector. The old preview remains clearly legacy/deprecated.

## Acceptance and completion evidence

Add named final-mesh fixtures for all 16 requested scenarios: rectangle gable,
hip, shed; rotated rectangle; parallelogram; trapezoid; general convex quad; L,
T, U; rotated L; oblique L/T; unequal-width join; terminating ridge; valley;
residential multiple-reflex outline. Include dimensions resembling residential
wings, not only unit grids. Flat and explicit part overrides also get coverage.

For each validate indices, nonzero face areas, no duplicate faces/vertices,
planarity, oriented edge/vertex manifoldness, no T-junctions, polygon projection
coverage/overlap, a single perimeter, deterministic output, translation/rotation
invariance, and equivalence after adding redundant collinear boundary vertices.
Check expected part counts and geometric ridge/hip/valley presence as well as
mesh metrics. Negative cases must raise unsupported without emitting a mesh.

Run the existing 79-test suite. Blender smoke must call the real source-object
entry and create all final mesh objects, use bmesh validation, UV unwrap and
material assignment, exercise object transforms and gridded sources, save a
reviewable .blend, and render representative L/T/U/oblique views for inspection.
Numeric success alone is not completion. Record exact commands/results and
remaining supported-domain limits in the README after implementation.

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
unchanged. A local installer was executed successfully with the distro Blender's
Python 3.13. Windows x64 wheels were verified on PyPI for 3.10–3.13, but Windows
Blender itself was not available for execution in this Linux workspace.

The representative smoke renders include separately derived facade objects for
context. Facades and render lights never enter the final roof mesh.

Final source-object transforms are multiplied in double precision using the
existing evaluated mesh read view; output vertex coordinates are stored relative
to the source world translation, not as large float32 world coordinates. Smoke
also exercises a rotated footprint translated by one million units. Generation
requires Object Mode, so no incomplete Edit Mode geometry/state is silently used.

## Validated delivery

The commands in the README were executed locally: 90 unit tests pass, including
all 79 baseline tests. Blender 4.3.2 created, validated and UV-unwrapped all 16
mandatory fixture meshes; transform, million-unit translation, gridded source
and existing-CLI checks also pass. Invalid nonplanar input leaves the scene
unchanged. Six final scenes were rendered and inspected: L, T, U, oblique L,
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

The canonical final-generation modules now live under `addon/roof_generator/core/`.
The addon uses its own metric mesh projection and Blender output importer; it
does not import the legacy SGA21 adapter or optimizer. Blender registration is
lazy so importing the geometry library outside Blender remains possible.
The sidebar conversion operator exposes type/pitch/eave offset, colors and source
visibility. Conversion is explicit and undoable, with no automatic handlers.
The ZIP installer smoke exercises the actual registered operator on all 16
fixtures, UV/material editability, transforms, failure without scene mutation,
and disable/re-enable lifecycle. This is the requested conversion-button option;
no live Geometry Nodes modifier is claimed.

All original datasets, MATLAB/UI files and copied Fig.7 fixtures have been removed.
The existing 79 optimizer/legacy regressions use a newly specified residential
hip graph where input files are needed. Original source links remain in
`reference/README.md` and the paper alignment guide. Own root commit metadata
does not transfer ownership of SGA21-derived code; license scopes are explicit
in `LICENSING.md`.
