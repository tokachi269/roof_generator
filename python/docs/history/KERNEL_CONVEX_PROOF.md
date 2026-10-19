# Historical snapshot

Scope: initial independent convex oracle; not the current full-Line scope at `62809e7`. This is not current authority.

# Initial kernel proof

## Executed first proof

Start SHA: `65a90cbab75560b7f70a1f6c6e3e652835a2a744`.
Contract commit: `01dbe51`; independent construction commit: `1929e5d`.

[roof_kernel_proof.py](../../roof_kernel_proof.py) is a development-only independent
oracle. It enumerates the vertices of the convex space-time body above by triples
of supporting constraints and extracts oriented inclined facets. A global time
cluster retains all contacts and all incident source IDs. It does **not** implement
an iterative event queue, reflex split or general contact rewrite. It uses bounded
floating-point algebra, not certified exact predicates. Its `O(n^4)` worst-case
enumeration is intended for small proofs and must not become the production kernel.

The original source path survives validation: no role transition is removed by
the current footprint analyzer. Full source identity/parameter range, EAVE/GABLE
role and event time are distinct data. Inclined patches alone enter the proof
mesh; stationary wall patches are not exported. All heights are event-derived,
without the ordinary skeleton, terminal-cap code or embedding solver.

The new five-edge nonparallel example is rejected by 1.5.0's automatic gable
selection (`no opposed-support terminal gable cap`). The explicitly declared
boundary proof produces two inclined facets, with nonconstant ridge height. This
compares construction capability, not identical architectural candidate policies:
1.5.0 has no equivalent explicit mixed boundary input API.

Independent tests exhaust all **498** nonempty eave subsets on convex 3–8-edge
paths. They check source-plane height, SVD planarity, positive normals, polygon
union, no interior overlap and event incidence. Square and regular hexagon
contacts preserve four/six incident source identities; rectangle contacts at the
same time remain two distinct locations. Source-aware winding/cyclic/rotation/
translation and repeated-run proofs pass. Budget exhaustion returns no prefix.
The concave single-eave counterexample has its own nonexistence certificate;
concave construction and partial collinear transitions are **outside this proof**,
not classified as mathematically invalid by a scope rejection.

The frozen [input records](../../tests/fixtures/kernel_line_proofs_v1.json) yield
five completed convex construction proofs, one nonexistence witness and two
construction/model probes outside the convex oracle. The concave all-eave input
has a known classical roof: its owner is proof/construction scope, not invalid or
ambiguous intent. The collinear partial-role input instead has an unspecified
model rule. The report keeps this distinction explicitly. Local full suite:
**246 tests pass**.
Blender 4.3.2 turns all five proof complexes directly into editable meshes with
planarity, manifold disk, normal, UV, material and source-provenance checks. Face
cycles and vertex count stay unchanged; no mesh repair is used. These are
development proof meshes, **not new addon-supported cases**.

| Proof input | Vertices | Patches | Positive-time clusters | Median ms (9 warm samples) |
| --- | ---: | ---: | ---: | ---: |
| Nonparallel full gables | 7 | 2 | 3 | 0.571 |
| Convex single eave | 5 | 1 | 3 | 0.376 |
| Square, all eave | 5 | 4 | 1 | 0.392 |
| Hexagon, all eave | 7 | 6 | 1 | 0.794 |
| Rectangle, two opposite gables | 6 | 2 | 1 | 0.185 |

Exact counts and raw timing samples are in [kernel/report.json](../kernel/report.json).
These tiny convex-oracle timings are neither production performance nor a
comparison to the existing generator's full candidate pipeline.

[Nonparallel boundary proof](../kernel/00.svg) and
[nonexistence witness](../kernel/05.svg) distinguish eaves (blue), gables (red) and
event contacts. The [Blender evidence](../kernel/blender-report.json) corresponds to
the image below. Render positions are for display only.

![Five independent proof roofs](../kernel/blender-meshes.png)

```bash
python python/probe_roof_kernel.py --output python/out/kernel-proof
python -m unittest python.tests.test_roof_kernel_proof -v
python -m unittest discover -s python/tests
blender -b --factory-startup --python-exit-code 1 --python python/blender_kernel_proof.py -- --output python/out/kernel-proof/blender
python python/build_addon.py --check --output packages/roof_generator-1.5.0.zip
```

The full-Line implementation now covers concave mixed-role propagation,
simultaneous contact incidence, stationary-remnant certificates and precision
refinement. The next production gates are universal zero-speed/completion
obligations, a sufficient admissibility/automatic intent policy, and addon
authority transfer. Partial-interval closure and Arc evolution remain later model
work. The necessary half-plane condition is not substituted for a sufficient
admissibility criterion. Production remains at 1.5.0; no "nonparallel cap" patch
or solver-based rescue has been introduced.
