# Roof-end authority

An analytic Cell contact is evidence of adjacency, not permission to create a
roof junction. `ResolvedArchitecture.with_ends` publishes compatible end states
and joint choices before composition. Shared choices determine compound Part
membership; extension choices leave receiver and branch as separate Parts.

## Research and implemented subset

[Hu et al. 2017, sections 3.4 and 3.5](https://www.researchgate.net/publication/319650645_Roof_model_recommendation_for_complex_buildings_based_on_combination_rules_and_symmetry_features_in_footprints)
constrains triangular roof sides at rectangle ends and couples symmetric roof
options. Its L relation admits shared and T options. R=0 forbids a triangular
roof side; it does not specify a completed geometric merge. This implementation
uses the gable-request subset: free ends are gabled, an extension consumes the
branch's internal gabled end, and a shared choice transfers both ends to a
compound junction. It does not implement Hu's full primitive probability model,
half-hip family, or independent options for all roof types.

[Sugihara 2007](https://www.jstage.jst.go.jp/article/journalac2003/16/0/16_0_309/_pdf)
describes extending a narrower branch into a wider receiver. The new isolated
corner-T operation reuses that extension incidence, with a literal four-face
witness and solver feasibility check. It requires one corner relation, a
strictly narrower leaf branch, and a complete branch-end contact. Equal-width
corner-T and multiple corner-T choices remain unsupported. Existing strictly
interior T/Cross and separated middle slots keep their previous incidence
contracts.

Laycock aggregation/merge remains mapped in
[the prior research document](ROOF_COMPOSITION_RESEARCH.md). The original paper
could not be reread in this investigation; that mapping does not establish a
new general offset or partial-end rule. No such rule was added.

## State, ownership, and construction

`roof_ends.py` separates an end's shape obligation from its connection. A gabled
shape with `extension` or `continuation` is not a surviving exterior gable cap.
Shared ownership cannot overwrite a conflicting obligation on the same end.
The global configuration intersects every relation's choices, then enforces
exact reflected whole-member end equalities. Partial reflected root matches
are not guessed. An assignment with no compatible configuration has no roof.

One-line obligations apply only to coincident full short ends, not staggered
partial end/end contacts. Those contacts fail with `offset_continuation` before
any end configuration is published. A general continuation RoofGraph rewrite
is still unimplemented. Parallel and partial-end relations also remain unsupported.

Composition receives the selected configuration. It binds published roles to
ports and validates operation applicability; it cannot turn an extension into
a shared terminal because that template is available. Compound composition
uses member incidence templates without constructing independent Cell roof
graphs. The solver receives fixed incidence and never chooses end states.

Architecture records include every compatible end choice before checking
operation availability. Rejections retain the chosen configuration. No valley
count, visual preference, or supported-operation bonus enters ranking. Equally
ranked constructible alternatives are seedable; therefore adding corner-T can
change the selected topology for an existing seed. Old candidate IDs and seed
choices on the old family remain regression constraints.

## Proofs and remaining limits

`test_roof_ends.py` independently fixes simultaneous conflicting obligations,
symmetry-coupled shared/T choices, selected configuration ownership, rejection
of an unsupported T without fallback, a literal narrow corner-T face incidence,
and rejection of forged end states. Internal branch caps do not survive as
gable-end edges; those edges must have physical boundary provenance.

Constraint feasibility and provenance do not prove a unique architectural roof
for an arbitrary footprint. The staggered, non-overlapping two-rectangle input
is still unsupported for both one-face and two-face Blender meshes. Its reported
factory roof was not reproduced. The representative render set is a sanity
check of recorded decisions, not a human aesthetics oracle.

Global configuration enumeration is finite but combinatorial. The generation
budget counts yielded end configurations along with axis assignments; rejected
combinations are currently enumerated before yielding. This is a scalability
limit, not a reason to select a partial-search winner.
