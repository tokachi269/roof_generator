# Recursive orthogonal roof regions

The active phase targets orthogonal gable generation: structured mesh/Blender
coverage at least 93/103, nonuniform at least 120/150, a substantial increase
from grid 5/1000, four screenshot approximations 4/4, and no regression of the
existing L/T/U/Cross/branch domain. These are product phase targets, not claims
that coverage proves architectural correctness. Nonorthogonal compound,
hip/shed expansion and performance rewrites remain outside this phase.

Published studies inform the architectural units. Missing general connections
may now be designed as explicit project rules with applicability, incidence,
counterexamples and independent embedding proof. Fixture rules, appearance
scores and unproved stitching remain prohibited. The existing skeleton
restriction still applies: aggregation guide only, never final roof topology.

## Implemented decomposition

`recursive_regions` selects inclusion-maximal contained receiver rectangles,
subtracts each receiver, and recursively decomposes every connected residual.
A rectangular residual terminates as a leaf. Every recursive call removes a
positive occupied region, so termination is structural, not a depth heuristic.
Coordinate boxes are temporary computation; accepted polygon supports go
through `propose_regions`. Minimum Cells are optional provenance only.

`RegionTree.region` references the canonical candidate's actual polygon.
Tree nodes do not keep a second copy of authoritative geometry. The shared
`region_boundary` validation binds input supports after the exact same
normalization used by the proposal contract, including noninteger dimensions.
Distinct ancestry is retained even when its support geometry is identical.
Geometry records are deduplicated; eventual roof-model/topology identity must
still be deduplicated by the candidate contract before seed selection.

Work and structure budgets explicitly bound the search. An incomplete search
publishes no usable structures. Exhausted search does not trigger another
source and cannot select a prefix. These are operation bounds, not wall-time
guarantees. No optimization or DP cache was added in this first implementation.

## Ancestry is not the complete contact graph

The image 3 approximation supplies an actual counterexample: a four-region
structure has three ancestry edges but four geometric contacts. Ancestor
receivers can touch several descendants across a residual component. The
contact graph must retain these cross-links; a tree walk cannot silently drop
them or assert an independent junction for every parent/child edge.

The next architecture stage must assign model directions, parent/child
connection semantics and all end obligations globally, then construct the
whole junction complex. Node count is not a count of independent gabled roofs.
The existing single-receiver composer is not this generic hierarchy grammar.

## Current evidence and limits

| Screenshot approximation | Distinct 2D geometries | Tree histories | Maximum depth |
| --- | ---: | ---: | ---: |
| 1 | 10 | 29 | 4 |
| 2 | 4 | 8 | 3 |
| 3 | 4 | 6 | 3 |
| 4 | 2 | 3 | 2 |

All four searches finish. Image 1 previously had no admissible proposal in the
single-receiver rectangular-residual family; it now has hierarchical supports.
Passing these polygons through the old model/end grammar still embeds only
images 2 and 4. This is a decomposition implementation, not a newly achieved
4/4 roof gate, and default roof coverage remains 5/1000, 1/150, 32/103.
The family is not yet wired into default seeded roof selection: hierarchical
architectural interpretations and generic compound incidence are still missing.

On all 103 frozen structured inputs, the bounded 2D search completes with
proposals on 93 and reports incomplete on 10. This is **not** 93 successful
roofs: the global architecture/graph/embedding stages have not been supplied by
this producer. [Structured evidence](authority/recursive/structured.json),
[four-input structures](authority/recursive/images.json) and
[old grammar comparison](authority/recursive/old-grammar.json) record the scopes.

Seven focused tests fix recursive residual handling, polygon ownership exactly
once, retained ancestry ambiguity, real cross-links, explicit budget failure,
input order invariance and noninteger boundary identity. The 184-test suite
passed after the shared boundary extraction; the final atomic-budget change
passed the seven focused tests. Previous `486abd6` CI passed all five jobs.

```sh
python -m unittest discover -s python/tests -p test_recursive_regions.py
python python/probe_recursive_regions.py --inputs python/tests/fixtures/user_roof_images_v1.json --output python/out/authority/recursive-images.json
python python/probe_recursive_regions.py --inputs python/docs/canonical/coverage_inputs_v1.json.gz --category structured_orthogonal --output python/out/authority/recursive-structured.json
```
