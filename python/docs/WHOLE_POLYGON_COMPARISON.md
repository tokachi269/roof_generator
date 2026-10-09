# Whole-polygon topology comparison

The controlled results support comparing a whole-polygon roof model rather
than adding more isolated rectangle junction operations. This is a prototype
decision, not promotion to the addon. The fixed comparison grammar is
`486abd60b1a44cadfaf419b787b7936bb3174908`.

## Causal result

All 1253 baseline inputs finished. Default selectable coverage remains grid
5/1000, nonuniform 1/150 and structured 32/103. A complete producer replay
agreed with the native audit on all 253 nonuniform/structured inputs before
being used for grid. Grid contains 827 inputs with no parallel-free modeled
assignment in either default source, not 999 inputs proved impossible because
of parallel. Another 17 are incomplete. The receiver source has 64 parallel-free
inputs; it removes parallel where minimum cannot in 32 inputs, but none of
those 32 reaches mesh. For structured, that same receiver change reaches mesh
in 11 of 27 such inputs. This separates upstream improvement from later grammar
failure.

Structured all-axis ablation keeps exactly the same 32 successful inputs, adds
none and loses none. Ten searches are incomplete. The full-corpus ablation is
still running and heavily censored by the original budget; its successful
prefix cannot establish an upper bound.

The 100 small-input rectangle-cover oracle finishes 99, embeds six and produces
zero graphs for the other 93. The remaining input exhausts its cover budget.
This is failure within the boundary-coordinate rectangle domain and unchanged
grammar, not proof that arbitrary polygons cannot have roofs.

The recursive producer with unchanged grammar is especially informative:
all 100 small inputs finish and have a parallel-free model assignment, but
only six embed. The other 94 reach ends (33) or composition (61). Structured
recursion embeds 32/103, with 30 incomplete searches. Nonuniform recursion
embeds 1/150, with 113 incomplete searches. The recursive source adds no
selectable inputs in these comparisons. Its source snapshot is `c53a815`;
relative to baseline, only the recursive producer and extraction of the
existing region-boundary function differ. End, composition and solver modules
are byte-equivalent after normalized line endings.

These experiments rule out treating rejected parallel incidence or recursion
alone as the explanation. The current rectangular model/end/composition
grammar is a measured barrier even when parallel can be avoided.

## Isolated backend

`whole_polygon_roofs.py` uses the already pinned developer-only
`py_straight_skeleton==0.1.0` to propose whole-polygon face incidence. Its gable
adjustment follows [Laycock and Day, section 6.1 and Figure 3](https://dspace.zcu.cz/bitstream/11025/991/1/G67.pdf):
terminal intersections move to their incident exterior edge midpoints. The
paper text and the local PDF figure were inspected. The probe restricts this
to triangular terminal faces with uniquely owned skeleton nodes. Shared-node
simultaneous caps remain explicitly unsupported.

Adjacent facets with an identical oriented supporting exterior line are
aggregated by their oriented cycles. Redundant degree-two points on a straight
interior crease are suppressed in both incident cycles. These are incidence
normalizations, not appearance scores or new rectangle junction rules. Every
final edge receives its explicit meaning from source slopes and oriented face
incidence before solving. The single polygon support has owner 0; minimum Cells
do not decide its face boundaries.

The complete RoofGraph then enters the unchanged `problem` and `solve` API.
Skeleton event times and external XYZ are not geometry anchors. The graph,
boundary, projection and mesh validators are not weakened. Exceptions are
recorded, without jitter, alternate generators or fallback. This model includes
hip edges and gable ends, as does the existing compound gable model. A mesh
success does not prove the desired architectural style.

Completed prototype results:

| Frozen inputs | Rectangle-cover oracle | Recursive/current grammar | Whole polygon |
| --- | ---: | ---: | ---: |
| Small sample 100 | 6, one incomplete | 6, complete | 81, all attempted |
| Structured 103 | not run | 32, 30 incomplete | 101, all attempted |
| Nonuniform 150 | 18 included in small sample | 1, 113 incomplete | 149, all attempted |
| Factory approximations 4 | previous domain probe | default addon 2 | 4, all attempted |

Small prototype failures comprise nine topology/dependency failures and ten
embedding failures. All ten embedding failures share a specific upstream
condition: a relocated terminal cap node also belongs to an additional source
facet beyond its two adjacent supporting lines. None of the 81 embedded inputs
has this condition. The source-slope metric witness at the original drawing
also has inconsistent incident heights in all ten. This does not prove that no
other embedding exists, but it invalidates treating these as ordinary terminal
adjustments or blaming initialization without further evidence. A generalized
simultaneous-end event is needed before changing the optimizer.
The two structured failures and single nonuniform failure
come from external skeleton antiparallel-event handling. Grid 1000 is still
being attempted and has no final coverage claim.

Blender 5.2.2 LTS validates and renders the four factory approximations and
the first six successful small-sample inputs. This tests exported prototype
meshes, not the addon operator. Colored overlays read the published graph
edge meanings: red ridge, yellow hip, blue valley. Ten selected images are a
sanity check; they are not a human scoring oracle. The geometry remains one
continuous roof rather than independent roofs capped at minimum Cell cuts.

## Remaining gate

Complete grid and axis measurements; resolve the ten small embedding failures
using the identified additional-facet cap domain.
Handle simultaneous skeleton events without input perturbation. Verify edge
semantics independently against solved slopes and transforms. Decide whether
this whole-polygon model supplies the intended gable architecture, including
its retained hips; do not equate high mesh coverage with architectural quality.
The optional dependency, execution cost and packaging remain outside the
stdlib-only addon contract. No production backend switch has occurred.

Commands (from repository root):

```powershell
python python/whole_polygon_roofs.py --code-root python/out/authority/causal-baseline-486abd6 --deps python/out/laycock-deps --inputs python/docs/authority/causal/causal-small-inputs.json --output python/out/authority/whole-polygon-small.json
python python/probe_recursive_roofs.py --code-root python/out/authority/causal-recursive-c53a815 --source-sha c53a815bdff00e47c43dcd45b82f04baa6015e70 --inputs python/docs/canonical/coverage_inputs_v1.json.gz --category structured_orthogonal --output python/out/authority/causal-recursive-structured.json
blender -b --factory-startup --python-exit-code 1 --python python/blender_topology_probe.py -- --report python/out/authority/whole-polygon-images.json --output-dir python/out/authority/blender-whole-polygon-images --limit 4
python -m unittest python.tests.test_whole_polygon_roofs python.tests.test_causal_frontier
python python/audit_gable_caps.py --report python/docs/authority/whole-polygon/whole-polygon-small.json.gz --output python/out/authority/gable-cap-frontier.json
python python/whole_polygon_batch.py --code-root python/out/authority/causal-baseline-486abd6 --deps python/out/laycock-deps --inputs python/docs/canonical/coverage_inputs_v1.json.gz --category orthogonal_grid_stress --resume python/out/authority/whole-polygon-grid.json --seconds 15 --output python/out/authority/whole-polygon-grid-bounded.json
```

The first unbounded grid probe stopped advancing on the twentieth input for
over ten minutes and was interrupted. The bounded batch isolates each input
with a 15-second wall budget. A timeout is `search_incomplete`, not unsupported,
and cannot establish impossibility. Its initial 19 completed rows are reused
only after checking corpus, prototype source, core hashes and exact prefix.
