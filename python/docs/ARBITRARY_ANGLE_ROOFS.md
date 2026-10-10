# Arbitrary-angle polygon roofs

## Geometry and model contract

Baseline: `21bd06a`. Footprint analysis, indexed Graph incidence, declared
support planes and fixed-plane embedding already use actual geometric directions.
The bounded bundled Straight Skeleton accepts normalized simple polygons;
the core wrapper currently rejects nonorthogonal input before calling it.

Two polygon model classes use the same incidence and downstream pipeline:

- **Hip:** every exterior edge is explicitly an eave. No gable selection,
  rectangular partition or axis preference is involved.
- **Terminal gable:** selected exterior edges replace oriented triangular caps
  by their two incident slope sectors. Each cap must have two unique sectors,
  and their inward unit normals must be opposed within `1e-8`. Other exterior
  edges are explicitly eaves. This is a mixed hip/gable model, not a promise
  of pure gables at every building end.

The local condition involves parallel support lines, not a 90-degree corner.
For equal pitch and eave height, their equality locus is the line midway between
the supports. A straight cap edge joining the supports meets that line at its
midpoint even when oblique. The preserved skeleton event lies on the same
locus. Thus the existing disk replacement and BoundaryPoint(edge, 0.5) remain
geometrically derived, without changing incidence after geometry solving.

Triangular incidence is a separate condition: opposed neighboring boundary
supports alone do not guarantee a triangular terminal cap. Unavailable or
conflicting disks must remain inspectable. No coordinate perturbation,
rectification, Boolean, alternate seed or runtime retry repairs a failed event.

## Exterior interpretation

Orthogonal gable requests retain the current rectangular guide and componentwise
axis preference, with unchanged candidate family and IDs. Single convex-quad
gable requests retain their existing two-direction primitive contract, including
nonparallel eaves. Neither minimum rectangle partition nor its cells are
generalized to arbitrary angles.

For other nonorthogonal gable requests, the architectural domain is explicitly
restricted to opposed-support terminal caps. Enumerate every maximal compatible
cap set, meaning no further admissible gable can be added without consuming
another cap's required slope sector. This uses the existing componentwise
gable-over-hip preference, without inventing long-axis or weighted scores.
Maximal independent sets of the cap conflict graph can be enumerated as maximal
cliques of its complement, using bounded Bron–Kerbosch traversal. All surviving
models must produce and validate Graph, GeometryProblem and mesh before stable
seed selection. Incomplete enumeration exposes no selectable prefix.

Inspect both geometric eligibility and backend feasibility. A polygon with no
opposed-support terminal cap fails a gable request; it is not converted to hip.
Hip is generated only when explicitly requested.

## Responsibility boundaries

`wavefront` produces bounded immutable incidence for a normalized simple polygon.
`PolygonRoof` declares exterior ends and roof type. Cap-domain selection operates
on exterior support relations and disk conflicts. `polygon_roof.topology` applies
the existing disk replacement, facet aggregation and indexed incidence contract.
`GeometryProblem` declares real source planes; `plane_embedding` solves fixed
coordinates. `RoofMesh` validates the unchanged cycles. Blender only exports them.

The rectangular hip analytic shortcut currently assumes a pre-anchored primitive
apex. A polygon-incidence square has a junction with no such preassigned height.
Fully declared hip planes must therefore use the existing linear embedding;
the geometry solver must not infer pitch from incomplete height initialization.
The independent rectangle hip witness remains a regression contract.

## Verification

Preserve all 21 baseline orthogonal candidates, rejection records and seed IDs
in the embedding benchmark. Check arbitrary-angle hip and terminal-gable
face incidence directly, independently verify equal-pitch plane distances,
planarity, projection union and boundary ownership. Use rotation/translation,
winding/cyclic start, redundant collinear vertices and stable reference direction
as metamorphic proofs. Shear supplies stress inputs, not an equivalence oracle.

Probe convex quadrilaterals, two-direction structures, trapezoidal/mixed-angle
branches and general simple polygons as separate fixed corpora. Record topology,
solve and mesh outcomes separately; backend event failures remain unsupported.
Installed Blender smoke must exercise concave nonorthogonal gable and hip roofs,
not just numeric Graph construction. Record latencies without profiling and
retain unchanged event/model budget behavior.

Generalized nonterminal, partial or nonparallel-support compound gables are
outside this extension. The existing nonparallel single-quad gable contract is
not evidence that the terminal-cap rewrite handles those compound cases.
