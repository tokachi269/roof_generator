# Polygon-authoritative region candidate contract

The polygon contract now reaches the shared composer through explicit region
models. The default footprint generator still proposes minimum partitions;
the skeleton diagnostic is not a runtime generator. The four-case production
gate remains unmet. See [composition evidence](ROOF_REGION_COMPOSITION.md).

## Authority and stages

`propose_regions(footprint, outlines, source=..., provenance=...)` is the public
proposal/2D acceptance path. Input outlines are in the original footprint's
world XY coordinates. Accepted `RoofRegion.boundary` polygons use that
footprint's shared intrinsic frame; their actual polygon is support authority.
Each optional `CellOverlap` records an intersection area against the supplied
source decomposition. A region may intersect fractions of several Cells, and
one Cell may contribute to several regions. No one-owner-per-Cell requirement
exists in this contract. The source decomposition is not mutated.

`RoofRegionCandidate` identifies a proposed region set. Its geometry ID excludes
source names, collection labels, input order and winding. It is not a final roof
candidate ID: two architectures on the same supports still need distinct model,
end-state and topology identity. Provenance describes the supplied partition;
it does not select roof axes, create relations or cause features.

`minimum_regions` is one producer using the same path. Explicit polygon
proposals are another producer. The inspection tool also imports **saved**
Laycock sensitivity proposals. These sources are compared as candidates, never
called sequentially as runtime fallback. No skeleton dependency enters core.

## Implemented geometric acceptance

Accepted supports are positive-area, connected simple orthogonal polygons,
aligned with the footprint axes. Holes, self-contact and multi-component input
are rejected. No component splitting, hole filling or leftover-area assignment
is performed. A temporary common-coordinate arrangement checks interior
ownership and rejects overlap, outside support and uncovered footprint.
It also computes Cell intersection provenance. This arrangement is computation
only; no semantic Atom membership or artificial feature boundary is created.

The core uses standard-library geometry and the existing normalized `EPS`.
Coordinate bands at or below `4*EPS` have no reliable interior midpoint and are
within the existing perimeter-normalized coordinate allowance. They are not
treated as architectural slivers or assigned a roof. A regression rejects a
gap above this allowance. This is coverage within numerical resolution, not
symbolic exact arithmetic. Complexity is O(nx ny (region edges + Cell edges));
it is a bounded-fixture implementation, not an optimized large-grid design.

Inspection explicitly reports `validation_stage = 2D support only` and
`roof_topology = None`. No method selects these records by seed and no
`valid_roof` field claims that geometry acceptance proves a roof.

`RegionPartGraph` consumes these polygons, declares rectangular gable model
axes, resolves global ends and reaches the same composer. Nonrectangular model
supports remain unsupported. The minimum-source `ArchitecturalPartGraph`
continues to validate its source-specific Cell interpretation. Neither path
forges a minimum Decomposition for a new polygon region.

## Recommendation domain

`parallel_recommendation(candidate, axes)` measures the Hu parallel term from
actual region polygons and explicitly declared model axes. For rectangular
long-axis supports, it counts positive-length long-side contacts and assigns
the published -2 term per pair. It does not inspect valley density or Cell
provenance. A nonrectangular support or a model axis outside that long-axis
primitive domain leaves the total score unknown (`None`), not zero. No area
score, fragment omission or general polygon prior is added.

This measurement is a recommendation probe, not an architectural validity
filter or roof-model assignment. Unknown scores cannot silently compete as
preferred zero-penalty candidates. None of these probes changes runtime ranking.

## Reproduced scenarios and limits

Before implementation, the central-region contract regression failed because
the API did not exist. Previously `ArchitecturalPartGraph` demanded member
bounds equal Cell bounds and Part boundaries equal canceled Cell boundaries.
The new regression accepts screenshot 4's central `(1,0)`–`(6,6)` rectangle
plus its left/right attachments. The central region's area is 30 input-unit²,
with 15 unit² from each of the two unchanged minimum Cells. This configuration
now has one embedded shared-end roof through the explicit proposal API; it is
not yet discovered by the default footprint generator.

The four screenshot sources pass through the same core contract:

| Screenshot | Distinct 2D candidates | Rejected source configurations |
| --- | ---: | ---: |
| 1 | 29 | 19 |
| 2 | 7 | 1 |
| 3 | 9 | 1 |
| 4 | 4 | 0 |

Minimum-source proposals duplicate geometry already present in the ordered
diagnostic family; they do not increase the distinct counts. Rejected
disconnected collections are not silently reinterpreted as separate regions.
The input frame, source minimum partition, actual boundaries, intersection
areas, source histories and recommendation probes are saved in
[the inspection report](authority/regions/candidates.json).

Screenshot 4 also exposes a remaining architecture problem: its old two
rectangles have one long-side contact (-2). Assigning independent long-axis
roofs to the central rectangle and both attachment rectangles produces two
such contacts (-4). Therefore a larger region alone does not establish a
better roof. Explicit transverse attachment axes remove those particular
parallel contacts, but the attachments then lie outside the scored long-axis
domain; their roof models and merge rules must be defined before selection.
The central candidate now passes model/end/graph/embedding validation with
explicit transverse attachment axes. Its unknown recommendation remains
unknown. This does not establish a general factory-roof repair.

Ten focused regressions cover partial Cell provenance, source/order-independent
geometry identity, the common producer contract, missing/overlapping/outside
area, a narrow gap, disconnected/self-touching input and score applicability.
The shared composer now reads indexed member supports. The explicit API was
also tested from an isolated installed ZIP; default candidate discovery is
still minimum-based.

## Next production gate

Migrate architectural support and member-model ownership to these actual
polygons, with source Cells retained only as provenance. Admit explicit model
families and supported merge incidence; resolve all end/symmetry constraints
before graph construction. Compare architectural recommendation separately
from constructibility and seed only complete valid roof candidates. The four
screenshot cases must reach RoofGraph → solve → installed Blender with an
integrated selectable configuration before this phase can be called the
factory-roof fix. Grid20/40 are outside this production gate.
