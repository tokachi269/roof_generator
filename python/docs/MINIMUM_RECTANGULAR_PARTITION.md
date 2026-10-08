# Classical minimum rectangular partition contract

## Scope and sources

Starting SHA: `9bec1849254ee12c303378a85966c769d4f3b7a0`.
This work replaces only the graph-first partition prototype. The production
plane/envelope route, its harness and roof topology composition remain unchanged.
Input is a normalized, hole-free, simple orthogonal polygon, including arbitrary
reflex count and rigid rotations via its intrinsic frame. Holes, point touching,
self intersections and nonorthogonal boundaries are rejected. The partition
layer has no roof-type, pitch, plane, ridge or solver input.

The implementation basis is [Eppstein, *Graph-Theoretic Solutions to Computational
Geometry Problems*, Section 3, PDF pp. 3–5](https://arxiv.org/pdf/0908.3916),
especially the good-diagonal definition, counting theorem, bipartite intersection
reduction and remaining-vertex completion on printed page 4. It attributes the
classical result to:

- [Lipski, Lodi, Luccio, Mugnai & Pagli (1979), *On two-dimensional data
  organization II*, Fundamenta Informaticae 2, 245–260](https://journals.sagepub.com/doi/10.3233/FI-1978-2116).
  Publication metadata was checked; the full text was not accessible.
- Ohtsuki (1982), *Minimum dissection of rectilinear regions*, ISCAS,
  1210–1213. The bibliographic attribution is verified in Eppstein reference 60
  and Liou et al. reference 15; the original full text was not available.
- [Ferrari, Sankar & Sklansky (1984), *Minimal rectangular partitions of
  digitized blobs*, CVGIP 28(1), 58–71](https://www.sciencedirect.com/science/article/pii/0734189X84901397).
  Its publisher abstract confirms the independent-set/matching reduction;
  the original full text was not available.

A second accessible primary source is [Liou, Tan & Lee (1990), *Minimum
rectangular partition problem for simple rectilinear polygons*, IEEE TCAD 9(7),
720–733, Section II](https://ir.lib.nycu.edu.tw/server/api/core/bitstreams/fa99356d-1701-4965-ae44-4199238328c8/content).
It explicitly lists the six classical steps and completion by extending incident
edges to existing cuts/boundary. Its faster method is associated with the
[1989 SoCG paper](https://doi.org/10.1145/73833.73871). We implement the transparent
classical reduction, not its specialized O(n log log n) data structures. No
claim is made to have read inaccessible original papers or to implement a new
minimum-partition algorithm.

## Algorithm and correctness obligations

Let n count corners after collinear normalization, r count reflex corners,
D be all good diagonals, M a maximum matching of the intersection graph, and
G a maximum disjoint subset of D. For this scope n=2r+4 and the optimum is

`R_min = n/2 - |G| - 1 = r - |G| + 1`, with `|G| = |D| - |M|`.

1. Extract all reflex vertices. A good diagonal is a nonzero horizontal/vertical
   segment between two distinct original reflex vertices whose **open segment**
   lies strictly inside the polygon. Boundary edges, exterior portions and any
   intermediate boundary contact are not good diagonals.
2. Enumerate each reflex's two inward incident-edge extensions. A good diagonal
   must end at the first boundary hit, otherwise its open segment would touch
   boundary. Keep hits at reflex vertices and deduplicate endpoint pairs. This
   ray enumeration is equivalent to checking every aligned reflex pair, not a
   greedy partition: no cut has yet been selected.
   First-hit visibility is evaluated once, not repeated for both endpoints:
   a parallel boundary edge's endpoint has a perpendicular incident edge and
   cannot be skipped by the boundary scan. The independent all-pairs/open-segment
   oracle verifies the resulting diagonal set.
3. Split diagonals by horizontal/vertical direction. Add a conflict whenever
   their **closed segments** meet, including a shared endpoint. Same-direction
   diagonals cannot overlap or share an endpoint: at a reflex there is only one
   inward ray for each axis, and a farther collinear endpoint beyond a boundary
   vertex would violate the open-interior definition. Thus all conflicts are
   across the two classes and the graph is bipartite.
4. Compute an ordinary maximum bipartite matching with deterministic ordered
   traversal (Hopcroft–Karp). From unmatched horizontal vertices follow unmatched
   edges H→V and matched edges V→H, obtaining reachable sets Z_H and Z_V.
   Minimum vertex cover is `(H\Z_H) union Z_V`; its complement, the selected
   independent set, is `Z_H union (V\Z_V)`. Retain the actual pairs and sets
   as an inspectable cardinality certificate.
5. Insert exactly the selected diagonals. Their endpoints resolve two reflex
   vertices each. For every remaining reflex, extend the vertical inward
   incident-edge direction in the intrinsic frame until the **nearest** original
   boundary or already inserted partition segment. The vertical choice is a
   deterministic instance of the completion freedom in the classical method,
   not a score, candidate search or greedy replacement of maximum matching.
6. Node the boundary and chosen cuts at their endpoints/Steiner junctions.
   Enumerate bounded face cycles by directed half-edge walks, preserving the
   collinear nodes that make the subdivision conforming. Remove collinear nodes
   only when determining each face's four geometric corners.
7. Require every bounded face to be a positive-area rectangle and the number
   of faces to equal R_min. Convert the subdivision to existing Cell/Side/
   Adjacency records with complete exterior intervals and artificial atomic
   intervals. Verify boundary/internal incidence and no unresolved reflex.

Why completion preserves the optimum: disjoint selected diagonals have distinct
endpoints, resolve 2|G| original reflex vertices and split the disk into |G|+1
regions. A completion starts at an unresolved original boundary corner and ends
at the first side of its current region; it resolves that corner without
crossing an existing cut or creating a new reflex. It cannot connect two
unresolved corners through free interior: that would be another good diagonal
disjoint from G, contradicting maximality (maximum implies maximal). Each of the
r−2|G| completions splits one region once, yielding
`1 + |G| + r - 2|G| = r - |G| + 1` rectangles. The counting lower bound from the
classical theorem is attained. Runtime assertions certify this construction;
independent small minima and independent geometric/matching oracles test it.

## Degeneracy and numerical rules

- Collinear original boundary vertices are normalized before counting n/r;
  their original edge IDs remain attached to exterior intervals.
- Multiple reflex vertices on one coordinate line are allowed. Only the first
  visible boundary endpoint in an inward ray can form a good diagonal. Do not
  create long diagonals through intermediate vertices, boundary overlaps or
  zero-length diagonals.
- A horizontal and vertical diagonal sharing an endpoint conflict. Selecting
  both would incorrectly count one reflex twice; proper crossings alone are
  insufficient. A diagonal endpoint on another diagonal's **open interior** is
  impossible for valid good diagonals: the endpoint is an original boundary
  point and the other's open segment is strictly interior. Reject such a
  candidate rather than perturbing the topology.
- Completion can stop on a selected diagonal or earlier completion and can
  create an interior T junction. Split the receiving segment at the same shared
  node; each resulting artificial atomic edge has exactly two incident cells.
  T junctions in the *geometric four-corner rectangle representation* are valid
  for the classical theorem. The noded cell boundary is conforming, with no
  unshared edge endpoint or dangling cut.
- Boundary hits create Steiner points. They split an original boundary edge
  into adjacent intervals; neither erase provenance nor introduce exterior gaps.
- Use the existing scale-normalized tolerance only to absorb floating-point
  rigid-transform error and share numerically identical points. Do not rectify
  nonorthogonal buildings or rasterize input. Guarantee statements apply to a
  simple orthogonal polygon whose distinct features are resolved by that
  tolerance; zero-length/touching/ambiguous degeneracies fail explicitly.
  Intersection checks first exclude disjoint bounding boxes conservatively
  expanded by 2*EPS: the existing narrow predicate allows at most EPS along a
  segment and EPS normal to it, so each coordinate allowance is at most 2*EPS.
  Proper intersections require unexpanded box overlap. This changes no accepted
  intersection, cut or optimum and is not a partition heuristic.

## Determinism and symmetry

Use canonical intrinsic ordering for diagonals/matching, vertical completion and
geometric ordering for cells/Steiner nodes. There is no aspect, cut-length or
roof-quality objective. Those may be studied later only among minimum partitions.
Parallel completions do not cross one another; their iteration order does not
choose a lower-cardinality partition.

Translation, cyclic start, winding, redundant collinear vertices and rigid
rotation preserve the geometric partition when its intrinsic axes are uniquely
defined (a half-turn ambiguity preserves the two axis classes). A genuinely
quarter-turn symmetric outline such as a regular cross can have asymmetric
minimum partitions. No deterministic function of that unlabelled outline can
both select one asymmetric minimum and be exactly equivariant under every
symmetry: applying the symmetry leaves the input unchanged but rotates the
selected partition. For these cases compare partitions modulo the outline's
actual rotational automorphisms, while still requiring the same minimum count,
coverage and provenance. A caller-supplied architectural axis would remove that
ambiguity in a future task; no silent heuristic can remove the mathematical
limitation. Exact physical-cut identity is still tested on asymmetric footprints.

## Implementation sequence and primary proof

Keep enumeration, matching, cut completion/face extraction and Cell assembly as
small functions, with intermediate inspectable output. A certificate records
reflex IDs, all diagonals, conflicts, matching, selected independent-set IDs,
completion segments and expected minimum count. RoofGraph generation is not
needed to partition or validate input.

Tests fix literal minimum counts for small shapes independently, use separate
geometry and exhaustive combinatorial oracles, and build test-only connected
cell outlines with one simple boundary. Hundreds of seeded unknown grid shapes,
long collinear runs, same-coordinate reflexes, endpoint conflicts, Steiner hits,
and 14–40-corner cases must pass rectangle/disjoint union, interval ownership,
adjacency, no dangling/reflex and cardinality proofs. Test generation and Shapely
remain outside the new runtime. Existing rectangle primitives and terminal-graft
proof stay; multi-cell roof composition and nonlinear solving are out of scope.

Retire the old single-reflex candidate selector only after the generic method
proves the same L has two valid cells and supplies that cell graph to the existing
terminal graft. Measure analysis, diagonal enumeration, intersection/matching,
completion/subdivision, Cell assembly and total uncached partition separately,
then a 1000-building batch. Stop at the proved generic cell graph.
