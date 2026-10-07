# Footprint → editable Blender roof

## Scope and architecture

The generator produces an editable planar roof surface from a simple footprint,
including convex quadrilaterals and concave, oblique multi-part outlines.
Roof types are flat, gable, hip and shed.

The conversion operator sends selected footprints to
`roof_generator.blender_output.generate_objects`. The single-object CLI uses
`generate_object`, which delegates to the same batch route. It reads evaluated
planar meshes once and calls `roof_generator.core.roof_building.generate_roof`
for each input before exporting validated surfaces. Geometry has one
implementation under `addon/roof_generator/core/`.

Partitions follow footprint edge directions and reflex vertices. Ridge, hip and
valley positions follow roof-plane intersections; architectural vertices are
derived from this geometry. Tessellation only exports the determined topology.

## Research and decisions

The following comparison identifies the partition, primitive and connection
choices used by the bounded roof-graph method.

| Source | Partition / evaluation | Primitive / connection / ridge, hip, valley | Decision |
| --- | --- | --- | --- |
| [Kada & McKinley 2009](https://www.isprs.org/proceedings/xxxviii/3-w4/pub/CMRT09_47.pdf), §§2.1–2.3 | Group nearly parallel outline lines, average a selected subset, avoid small cells. | Parameterized flat/shed/gable/hip/Berliner blocks, LiDAR normal votes and parameter fitting; replace junction blocks using neighboring fits. | Adopt small parts, provenance and adjacency. Reject footprint generalization, LiDAR dependency and corner/T/cross junction classes. |
| [Laycock & Day 2003](https://www.sthu.org/misc/SKRW14/papers/LaycockDay_2003_AutomaticallyGeneratingRoofModelsBuildingFootprints.pdf), §§6–7 | Rectilinear reflex rays; grow/merge rectangles from skeleton lines. | Hip from inward skeleton and supporting-edge distance; gable changes end slopes; merges roofs. | Adopt supporting-edge planes and reflex candidates. Do not port midpoint skeleton editing or rectilinear-only partitioning. |
| [Sugihara & Hayashi 2006](https://www.jstage.jst.go.jp/article/journalac2003/15/0/15_0_67/_pdf), §3; [2007](https://www.jstage.jst.go.jp/article/journalac2003/16/0/16_0_309/_pdf), §3 | RL expression identifies reflex cuts; select branches with good aspect ratios to avoid strips and excessive subdivision. | Rectangular roof solids, Boolean assembly; narrower roofs extend toward wider roofs. | Adopt reflex cuts and explicit aspect objective. Reject RL shape cases, right-angle rectification and rectangle-only primitives. |
| [Kelly & Wonka 2011](https://www.peterwonka.net/Publications/pdfs/2011.TOG.Kelly.ProceduralExtrusions.TechreportVersion.final.pdf), §4 | Input plan plus per-edge profiles, rather than optimizing a quad partition. | Sweep direction planes; events change active-plan topology; halfedges assemble planar faces, including holes; ridge arcs arise at plane events. | Adopt plane-defined geometry and shared topology. Full event machinery for negative offsets, dormers and profiles is beyond the four requested roof types. |
| [twak/campskeleton](https://github.com/twak/campskeleton), [twak/siteplan](https://github.com/twak/siteplan) | Weighted skeleton / procedural plan and profile editing, not a minimal architectural-part partition solver. | Java robust event processing and direction planes; siteplan adds profile events and shell editing. | Apache-2.0. JVM/Maven and Java GUI/runtime requirements complicate Blender packaging, including Windows. |
| [CGAL skeleton](https://doc.cgal.org/latest/Straight_skeleton_2/index.html), [partition](https://doc.cgal.org/latest/Partition_2/index.html) | Optimal convex partition or approximation (not constrained to architectural quads); inward edge events / positive weights. | Skeleton regions belong to source edges; event arcs lift onto roof planes. | Strong optional future backend. Full concave skeleton is not equivalent to a global minimum of infinite edge planes. Avoid silently approximating it that way. C++ bindings, ABI/builds and GPL/commercial package licensing need separate distribution work. |

GEOS/Shapely validates input/output geometry, records the winning partition's
adjacency/provenance, and performs constrained triangulation for faces with holes. Shapely 2.1.2 has BSD licensing; its GEOS wheel libraries are LGPL
and dynamically loaded. Windows x64 and Linux wheels are available for the
supported CPython versions. `requirements-roof.txt` pins Shapely 2.1.2.
The addon preferences and `install_roof_dependencies.py` use host Python with pip
to install a wheel matching Blender's CPython under `.roof-deps/cpNNN`.
GEOS provides independent polygon validity/coverage checks. Part selection and
roof graph construction use scalar ring, chord and line-interval calculations.

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
an interior segment. Follow the two boundary arcs around a known chord using
ordered coordinate tuples. Candidate exploration constructs no Polygon objects.
Recursively enumerate these ring partitions until parts are convex
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
Create polygons only for the winning rings, then validate their area coverage
and disjoint interiors. Adjacency is positive-length shared
boundary, including partial boundary overlaps, never a guessed nearest neighbor.

Partitioning depends on the immutable normalized polygon, source-edge provenance,
roof type and search limits. A bounded cache retains up to 256 such partitions.
Pitch, eave height and explicit planes are applied from the current request;
they do not trigger another partition search or reuse prior request parameters.
The 2D graph has a separate bounded cache for roof shape. A common positive
vertical scaling/translation preserves its XY topology, so uniform pitch and
eave edits restore the requested face planes and embed the cached graph.
Relative part pitches/heights, explicit planes, type and orientation participate
in the shape key. Current parameters and source identities are always restored;
full mesh validation runs on every request.

Pure polygon facts (cleaned boundary, reflex vertices, cyclic signature and
geometric properties) have bounded caches. Convexity queries do not compute a
minimum-area bounding rectangle. Gable/shed searches reject triangle-producing
cuts before full candidate validation. After solving one side of a cut, remaining
part-count, aspect-ratio and cut-length lower bounds prune only branches that
cannot improve the current lexicographic result. These optimizations retain the
selection criteria and numerical tolerance; they do not simplify the footprint.

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

The exposed roof is the upper envelope of the parts' lower-envelope supports.
Its graph is constructed directly in XY:

1. Represent each solid's domain and active-face conditions as affine inequalities.
2. Bound equal-height lines by the two active faces' domain/plane constraints.
3. Intersect those line intervals with the footprint and subtract intervals where
   another solid is higher. These are interval operations, not polygon Booleans.
4. Include domain-transition lines to detect terminating roofs and height steps.
5. Node surviving segments and exterior edges, share intersection vertices,
   and walk angle-ordered halfedges to obtain face cycles.
6. Remove construction edges separating the same plane and straight degree-two
   waypoints. Keep all junctions and the face ownership/adjacency they determine.

Each source edge carries its original footprint support line. Partial part edges
use that same line, so near-collinear cleanup cannot create competing numerical
eave lines. No L/T/U class or shape-dependent connection rule participates.

`RoofGraph` stores XY vertices, outer/hole face cycles, associated face planes,
owners and shared edges. It stays two-dimensional until `embed()` solves each
vertex height from its incident affine face constraints. All incident heights
must agree within tolerance. Unsupported height steps or inconsistent face
cycles fail before Blender output. Requested pitch ratios/heights can affect the
2D graph; topology is not claimed to be independent of those constraints.

This direct embedding is sufficient for the four supported parametric roof
families. Ren et al. (2021) optimizes an already specified graph when its embedding
is unknown; no nonlinear planarity optimizer is required when the chosen support
planes already determine a planar embedding.

This is a documented roof interpretation, not recovery of an unknown real roof
from footprint alone. Explicit part parameters permit other pitch/orientation
choices. Reject connector arrangements that cannot produce a continuous surface.

## Topology and mesh data flow

`Blender planar mesh → plane frame / boundary → normalized ring → chord search
→ RoofParts / adjacency / source support lines → 2D RoofGraph / face cycles
→ affine 3D embedding → graph mesh export → mandatory validation
→ one Blender mesh object per footprint`.

The graph owns indexed connectivity; planar regions are derived from its cycles
for analysis. Ordinary face cycles become n-gons directly. Faces with holes use
GEOS constrained Delaunay only at mesh export. The exporter introduces no roof
features or topology decisions. Creases are classified on shared graph edges by
the incident planes: opposing/horizontal convex crease = ridge, other convex
crease = hip, concave crease = valley. Coplanar tessellation edges have no roof
feature. Debug lines, caps and hidden faces never enter the roof surface.

A roof surface is a two-manifold **with one intentional perimeter boundary**.
It is not a closed volume: no underside/building walls are requested. Validation
requires exactly one perimeter matching the footprint and two oppositely directed
incidences per internal edge. This distinguishes intended eaves/gable ends from
holes or nonmanifold junctions.

The generator creates planar faces directly from affine roof planes and validates
them before export.

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

Blender smoke calls the addon mesh API and the footprint CLI, creates and validates
the final meshes, unwraps UVs and
assigns materials. It exercises object transforms and gridded sources, saves a
reviewable .blend, and renders representative L/T/U/oblique views for inspection.

## Implemented numerical and deployment boundaries

Intrinsic coordinates are divided by perimeter. Input and winning-part arithmetic
use a `1e-11` precision grid. Graph predicates use `2e-9` as numerical tolerance;
node sharing uses four times it, and mandatory validation bounds residuals at
twenty times it. These are numerical allowances, not architectural cost weights.
Intersection nodes are shared before cycle construction. Heights come from
incident support planes; inconsistent heights fail rather than being averaged.

The final Blender entry hides, but retains, the input footprint after successful
import, including in renders. It makes no topology repairs. The footprint CLI
uses the same conversion API with `--roof-type`, pitch and eave-height parameters.
Windows x64 wheels support CPython 3.10–3.13.
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

The validation suite contains 30 tests covering the 16 fixtures,
roof types, transforms, topology invariants and unsupported inputs.
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

Maximum measured float32 Blender face planarity error: `4.25e-07` world
units (smoke limit `2e-5`). Saved outputs are reproducible generated artifacts
under ignored `python/out/acceptance`, not fixture-specific production
geometry. `all_roofs.blend` holds the ordinary editable meshes; individual
representative scenes add separate walls/lights for visual review.

## Standalone addon delivery

The final-generation modules reside under `addon/roof_generator/core/`.
The addon uses metric mesh projection and a Blender output importer. Registration is
lazy so importing the geometry library outside Blender remains possible.
The sidebar converts one or multiple selected footprints. A batch evaluates its
inputs once and validates all requested roofs before changing the scene. Invalid
input leaves object and visibility state unchanged. The operator exposes
type/pitch/eave offset, colors and source
visibility. Conversion is explicit and undoable, with no automatic handlers.
The ZIP installer smoke exercises the actual registered operator on all 16
fixtures, UV/material editability, transforms, failure without scene mutation,
and disable/re-enable lifecycle.

Final-mesh inputs are defined in `python/tests/fixtures/roof_acceptance.json`.
Source and research references are in `reference/README.md`. Project licenses
and dependency conditions are defined in `LICENSING.md`.
