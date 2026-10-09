# Declared region composition and global roof end choices

Starting revision: `3973235`. This phase evaluates two explicit alternatives
without changing the addon, its canonical backend, solver or package. The
local-composition experiment improves some gable structures but remains far
below the whole-polygon prototype's construction coverage. The global cap-end
experiment constructs all 84 previously conflicting shared-cap inputs.
Neither result establishes an architectural recommendation or production
acceptance. Retaining one hip is an explicit candidate decision, not a runtime
fallback after a failed gable.

## Local composition experiment

`hybrid_roofs.py` accepts actual rectangular RoofRegions and explicit axes.
Contacts declare receiving side attachments, partial end attachments or
end-to-end contacts before geometry is intersected. Long-side parallel roofs
are not accepted as independent members. Narrower-to-wider is recorded, not
promoted to a hard validity constraint. There is no largest-area priority.

The recursive region producer supplies candidate covers. Both axes remain in
the model domain, without the old end CSP, symmetry restriction or junction
templates. Each branch strip extends into its declared receiving slope, up to
the receiver ridge. It does not reappear on the opposite slope. Within each
receiver only that model and its explicitly declared attached branches take
part in the solid union. All attachments are composed simultaneously. Source
face intersections are exact rational halfplane cuts. Coplanar edge-connected
patches are aggregated; holes, discontinuities and nonmanifold events are
rejected without welding, jitter or geometry repair.

The resulting complete RoofGraph has exterior eave support and declared
crease semantics before `problem()` and `solve()`. The same graph object must
survive solving. Part boundaries do not become final creases automatically.
Member provenance is reported separately; the graph represents the composed
roof, rather than treating every rectangle as a final architectural owner.

This is a rectangle + declared extension comparator, **not** a complete
implementation of Laycock's region aggregation or a global wavefront. The
diagnostic uses exact decimal input in a cardinal source frame; arbitrary
rotations are outside its current input contract. Tests cover source reversal,
start-index change, translation, scale and quarter rotation. No new geometric
snapping or tolerance-based facet welding is used.

### Frozen corpus results

| Corpus | Old rectangle grammar | Local composition | Whole-polygon at 3973235 |
| --- | ---: | ---: | ---: |
| Small orthogonal 100 | 6 | 24 | 91 |
| Structured 103 | 32 | 63 | 101 |
| Nonuniform 150 | 1 | 2 | 149 |
| Factory screenshot approximations 4 | 2 | 3 | 4 |

Counts mean constructed/embedded witnesses, not architectural quality. The
small comparator uses the same complete recursive cover producer as the
earlier 6/100 recursive experiment. All six previous successes are retained;
18 additional inputs now embed. All 76 remaining small inputs finish at
composition, with exact contact-profile mismatch, internal height
discontinuity, or missing exterior support. They do not fail because a named
junction template is missing. This does **not** prove impossibility for all
rectangular roof architectures: other decomposition families, model types and
extension semantics are outside this experiment.

The local experiment stops after its first verified witness. This certifies
existence and is not seed selection or a complete pool of roof alternatives.
`search_complete=false` on those witness rows means alternatives were not
exhausted. No first-witness ordering is an architectural recommendation.

The structured local result has 20 incomplete inputs; the nonuniform result
has 103. Incomplete cases are censored, not unsupported or proofs of model
impossibility. A 15-second subprocess budget bounds each input. Region-work
and axis-assignment budgets are also explicit in the worker. These figures
show a substantial remaining producer/search limitation on larger polygons;
they must not be read as intrinsic 2/150 expressiveness of rectangle models.
No full 1000-grid local-composition run is claimed.

Exact contact-profile preflight is a construction check: it evaluates every
breakpoint and open interval of the declared piecewise-affine profiles. It
cannot reject a compatible profile merely because an old relation label is
unsupported. It avoids constructing a 2D arrangement already disproved by
its source geometry; it is not aesthetic filtering.

Successful small calls have median 0.265 s and maximum 1.211 s; structured
calls median 0.247 s and maximum 6.069 s. These are one worker call per input,
including region discovery/composition/embedding but excluding process import
and startup. Concurrent diagnostic jobs ran during collection. They are
descriptive timings, not controlled warm/cold performance acceptance. No
optimization or interactive latency claim is made.

### Visual and independent semantic checks

Blender 5.2.2 LTS validated and rendered ten identical-input pairs. Selection:
three constructed screenshot approximations, U/Cross/comb first variants, one
previous small success (`generated_0024`) and the first three new grid witnesses
(`generated_0044`, `generated_0047`, `generated_0122`). Both methods use the same
camera/render path. All twenty renders were inspected. Red is ridge, blue
valley and yellow hip. These are exported prototype meshes, not addon operator
acceptance.

- [First five pairs](authority/hybrid/hybrid-pairs-1.png)
- [Next five pairs](authority/hybrid/hybrid-pairs-2.png)

Local composition removes hips and produces continuous gables in several
paired examples, including U and screenshot approximations 2/4. Cross is
similar under both methods. Some compound examples retain substantially more
gable branch peaks/valleys than the whole-polygon version; fewer hips alone
does not establish the desired architecture.

Screenshot approximation 1 embeds and passes native mesh validation, but
three external edges marked `gable_end` have no boundary ridge endpoint.
The independent semantic diagnostic flags this case. Its irregular external
gable cut is a quality limitation; do not promote the 3/4 mesh result to 3/4
accepted architectural roofs. There are no valleys with both endpoints at
eave height among the inspected outputs.

## Global explicit end-choice experiment

`whole_polygon_roofs.topology(..., selected_caps=...)` accepts an explicit
terminal-cap set. The default all-cap policy remains unchanged. A selection
must refer to available caps; the oriented disk replacement still requires
two unique surviving neighboring slope sectors. This permits compatible
simultaneous decisions, including opposite gables sharing a square event,
without duplicating or moving a shared junction arbitrarily.

The frozen 84 failing grid inputs have 86 shared events, each with two adjacent
caps. Each such event gets two explicit intentions: A gable/B hip and B
gable/A hip. Other original terminal gable intentions remain fixed. The full
Cartesian product is constructed before any result is inspected, and **all**
alternatives are tested. No successful alternative wins by traversal order,
area, score, appearance or a solver-derived decision.

**84/84 inputs, 172/172 declared alternatives embed.** There are no graph,
geometry-problem or embedding rejections. Independent solved-facet checks
find zero semantic disagreements and zero eave-height valleys in these 172
outputs. Four Blender renders cover both alternatives for the first two
frozen inputs; all were inspected. The visible difference is the explicitly
chosen gable/hip end. Complex examples still retain many hips.

The original 84 failures therefore do not require a new junction template for
these alternative intents. The uniform all-cap intention was incompatible.
However, this experiment does **not** decide which end is architecturally
preferable, derive that decision from regions, enumerate all possible roof
models, or implement a delayed/weighted skeleton. It does not change default
coverage from 741 to 825 or solve the dependency's antiparallel events. The
new 172 alternatives are construction evidence, not a selectable production
candidate pool.

## Decision and next boundary

Keep whole-polygon topology as the current leading construction route, and
retain local region composition as a comparator. Its good gable examples are
useful references for exterior end intent; its low broad construction coverage
does not support replacing the global route with this local family.

The next contract is:

```text
region/axis interpretation
  -> exterior edge or interval intent (eave/gable/alternative)
  -> compatible global end configurations
  -> complete RoofGraph
  -> unchanged GeometryProblem and solve
```

Region intent must be explicit and its unrepresented intervals visible. A
minimum Cell is provenance, not authority that every partition must leave a
roof junction. Symmetric or genuinely ambiguous end choices remain candidates;
implementation order must not settle them. Partial-edge intent may require
boundary subdivision and cannot be silently approximated by a whole-edge cap.

A genuine delayed wavefront is a later comparison, not this postprocess under
a new name. The installed ordinary skeleton dependency has no weighted API.
Robust simultaneous/antiparallel events, intended architecture, complete seed
alternatives, performance and packaging remain production gates.

## Research and project adaptations

[Laycock & Day (2003), Section 7](https://dspace.zcu.cz/bitstream/11025/991/1/G67.pdf)
aggregates elementary rectangles into regions before assigning and merging
roof models. Its examples do not specify this experiment's exact arbitrary
partial-end union rule or a complete simultaneous face arrangement.
[Sugihara & Hayashi (2007), pp. 312–313](https://www.jstage.jst.go.jp/article/journalac2003/16/0/16_0_309/_pdf)
describes a narrower branch extending toward a wider, higher main under a
common slope. The local exact surface compositor above is an explicit project
adaptation, not a verbatim published construction algorithm.
[Held & Palfrader](https://arxiv.org/html/1604.03362), Sections 3–4, describes
delayed wavefront motion and gables without postprocessing. That supports
investigating a global end-intent route; it does not establish correctness of
this project's cap postprocess or supply a working weighted dependency.

## Reproduction

From the repository root:

```powershell
python python/hybrid_batch.py --code-root . --inputs python/docs/authority/causal/causal-small-inputs.json --output python/out/authority/hybrid-small-bounded.json
python python/hybrid_batch.py --code-root . --inputs python/docs/canonical/coverage_inputs_v1.json.gz --category structured_orthogonal --output python/out/authority/hybrid-structured-bounded.json
python python/hybrid_batch.py --code-root . --inputs python/docs/canonical/coverage_inputs_v1.json.gz --category nonuniform_orthogonal --output python/out/authority/hybrid-nonuniform-bounded.json
python python/probe_hybrid_roofs.py --code-root . --inputs python/tests/fixtures/user_roof_images_v1.json --output python/out/authority/hybrid-images.json
python python/probe_cap_choices.py --code-root . --deps python/out/laycock-deps --corpus python/docs/canonical/coverage_inputs_v1.json.gz --frontier python/docs/authority/whole-polygon/multiple-cap-frontier.json --output python/out/authority/cap-choices.json
python -m unittest python.tests.test_hybrid_roofs python.tests.test_whole_polygon_roofs
python -m unittest discover -s python/tests
```

Frozen reports, paired input receipts, prototype source hashes and Blender
images are in `authority/hybrid/`. Nine new contract checks cover extension
reach, narrow/equal/opposite/nested branches, unchanged graph identity,
discontinuous offset ends, transforms, explicit retained hip and compatible
shared square events. Full suite: **201 tests pass**. The addon source and ZIP
are unchanged; this milestone has not promoted a generator backend.
