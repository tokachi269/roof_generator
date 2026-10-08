# Initial graph-first rectangle / terminal-attachment evaluation

The partition prototype described below has been replaced by the
[classical minimum rectangular partition](MINIMUM_RECTANGULAR_PARTITION.md).
The initial evaluation and its recorded timings remain historical evidence.
Current partition accepts arbitrary reflex count; roof composition still stops
at the proved terminal two-cell case.

## Scope and decision owners

Starting production commit: `1de443f53740a5a71e5512f421b691d0e7a256f5`.
The independent path is `python/graph_first/`; no addon core, distribution ZIP,
existing test, semantic harness or performance harness is modified.
This evaluation stops at rectangle meshes and the pre-solver graph of a
single terminal attachment of two orthogonal rectangular cells. T/U, oblique
cells, mixed roof types and multi-attachment composition are not claimed.

| Decision | Owner | Authoritative output |
| --- | --- | --- |
| Normalize and analyse the outline | footprint | Ordered vertices, directions, reflex IDs, original-edge provenance, intrinsic frame |
| Select a partition | cells | Rectangular corners, noded cell boundaries, exterior/artificial intervals and adjacency |
| Select primitive connectivity and join it | topology | Indexed face cycles, shared edges and ridge/hip/valley meanings |
| Embed fixed connectivity | geometry | Geometry problem; analytic rectangle coordinates and mesh export |

The graph stores no affine roof planes. Neither primitive composition nor mesh
conversion recovers semantics from height comparisons. The solver may move
allowed coordinates but cannot add faces/edges or change connection types.
Mesh coordinates are validated against that same graph for fixed boundary,
noncrossing footprint projection, distinct vertices, positive planar faces and
consistent normals; export never repairs or substitutes connectivity.

## Research used in this evaluation

Ren et al., *Intuitive and Efficient Roof Modeling for Reconstruction and
Synthesis* (2021), uses an authored roof graph followed by a valid 3D embedding.
The historical local implementation at `a0c8b36` had `RoofEmbeddingInput`
(variable XY IDs, variable Z IDs, initial/reference vertices, face cycles),
`roof_core.py` (sum of smallest face-covariance eigenvalues, optional XY
regularization, finite-difference BFGS), and `roof_dual.py` (dual face adjacency
to primal incidence, then Laplacian initialization). These identify reusable
contracts and mathematical ideas. No historical module is restored or imported.
The referenced source is CC BY-NC 4.0; it remains an external reference.

The mathematical planarity objective and variable selection, rather than a
copied optimizer or Blender-role adapter, are the future nonlinear solver
boundary. Planarity alone admits a flat solution: nonzero ridge-height anchors
and the fixed footprint/eaves must be supplied explicitly. A graph's oriented
disk contract is necessary but does not by itself prove a valid 3D embedding.
This scope exports that problem for L; it does not claim an integrated nonlinear
L solver. Rectangles use the explicitly permitted analytic solution.

Laycock & Day's reflex-ray partition construction and Sugihara & Hayashi's
avoidance of extreme rectangular pieces inform the cell selection. For one
reflex vertex, test the two inward extensions of its incident edge directions.
A valid chord follows the two original boundary arcs into two rectangles.
One rectangle cannot contain a reflex vertex, so two is the minimum here.
Compare only worst cell aspect ratios, then cut length and a stable signature.
No recursive partition tree, completed-roof candidate or weighted score is used.
This is not an implementation of a general minimum-rectangle-partition theorem.

Kada & McKinley's architectural parts motivate explicit cell adjacency and edge
provenance. Kelly & Wonka's sweep/event machinery, campskeleton, siteplan and
CGAL straight/weighted skeletons are not topology backends or fallbacks here.
No wavefront or polygon/solid Boolean is used in this route.

The [wire agent harness](https://github.com/tokachi269/wire/blob/master/docs/engineering/agent_harness.md),
[testing policy](https://github.com/tokachi269/wire/blob/master/docs/testing.md) and
[wire testing](https://github.com/tokachi269/wire/blob/master/docs/wire/testing.md)
inform decision ownership, independent primary proofs, semantic fault injection
and metamorphic checks. No framework, ledger or manifest is copied.

## Primitive composition

A gable rectangle has two slope-face cycles and a ridge connecting its two
gable ports. Eave-pair selection uses actual exterior-edge presence, then side
length; it does not depend on roof planes or pitch. Hip adds corner-to-ridge
edges (a square uses one apex); flat/shed have a single face.
Shed supports an explicit low-eave edge ID. A symmetric rectangle cannot define
an inherent directed slope; metamorphic proofs supply the same physical low
eave after each transform. The default tie-break is deterministic in the
normalized frame, but does not promise a directional choice invariant under
every permutation of an otherwise symmetric input.

A terminal attachment requires a complete branch gable side matching a partial
host eave side, perpendicular ridge directions, and exactly one end of the
shared interval touching a host corner. The continued exterior eave determines
which near host gable port terminates inside the connection. Splice primitive
cycles, remove the artificial boundary, and connect the two surviving ridge
ports, convex exterior corner and reflex shared-boundary endpoint to a junction.
The new corner spoke is hip; the reflex spoke is valley. These are graph meanings
selected before any Z coordinates exist.

For equal transverse widths, this is a degree-four junction. For unequal widths
under the evaluation's common-pitch/eave interpretation, refine it into two
degree-three junctions: the wider ridge and convex spoke attach to one vertex,
the narrower ridge and valley to the other; a hip joins them. Refinement replaces
one vertex in incident face cycles; it does not intersect roof planes. Width
ordering is a genuine topology transition at equality, not a claim of topology
invariance across every dimensional change. Initial XY is a disposable Laplacian
embedding constrained to the declared primitive ridge directions, not the result
of a height envelope or a final roof coordinate solve. An unconstrained harmonic
embedding can send a connector outside a concave footprint. Even an
axis-constrained drawing can cross the re-entrant boundary for long arms with
similar widths. A scalar drawing guard checks crossings, positive cycles and
interior spokes. If needed, backtrack the same two junctions along their declared
axes towards the common axis intersection; never emit the coincident limit.
This changes only disposable initial XY, not topology, and fails explicitly if
no nondegenerate drawing exists. Independent polygon coverage proofs test that
guard. Ridge directions come from source eaves, not optimized coordinates.

Face cell IDs identify originating primitive faces. They do not claim the
geometric visible-solid contributor semantics of the reference's `face_parts`.
Every exterior segment retains its actual input-edge interval/provenance, and
each shared junction retains both incident cells. This distinction is reported
in the secondary comparison rather than forcing the contracts to agree.

## Proof and stop condition

Primary proof inspects face incidence, a single boundary loop, Euler disk
characteristic, boundary ownership, source cell ownership, ridge/valley spokes
and junction degree directly. Known rectangle and unequal-width terminal graphs
have independent expected incidences; deliberate semantic/incidence faults must
fail. Tests cover translation, rotation, cyclic start, winding and redundant
collinear vertices, with provenance compared geometrically after undoing the
known transforms. Metric geometry and connectivity are not conflated.

The existing unmodified semantic harness is a secondary comparison. Rectangle
analytic meshes can be compared completely; L's pre-solver graph can be compared
only on topology/semantics, not on final planes or optimized XYZ. Report that
scope explicitly. Graph construction is measured uncached and without a
profiler. An import boundary proof must demonstrate that the new route runs
without Shapely or the legacy core.

Proceed to T/U only after terminal composition has an inspectable disk and its
provenance, semantic and metamorphic proofs pass. A middle-interval attachment
and interacting multiple attachments need their own graph operation proofs;
passing L does not automatically prove those rules or a nonlinear solver.
