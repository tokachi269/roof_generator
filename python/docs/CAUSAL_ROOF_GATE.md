# Coverage cause and model-family decision gate

The active objective is to determine why most frozen orthogonal inputs cannot
be expressed by the current roof model and topology grammar, then select a
production direction using measured evidence. Recursive receiver expansion is
no longer assumed to be that direction. Further production junction additions,
solver changes, mesh changes and performance rewrites are suspended until this
gate has a result. Existing uncommitted hierarchy work is an experiment, not a
released general generator.

## Fixed comparison

Use `486abd60b1a44cadfaf419b787b7936bb3174908` as the pinned baseline. Export its
source separately; diagnostic changes do not modify its files. Baseline and
all-axis runs use the same frozen grid 1000, nonuniform 150 and structured 103
inputs, identical budgets and unchanged end/topology/geometry/embedding rules.
Both axes are permitted only in the diagnostic minimum rectangular models.
The immutable model validator's duplicate long-axis assertion is relaxed in
that diagnostic process; all its other validations remain. Receiver proposals
and their model restriction remain unchanged in this controlled ablation.

The pre-gate hierarchy experiment measured grid 6/1000, nonuniform 1/150 and
structured 42/103. Recursive polygons through all-axis models measured 42/103
selectable structured inputs, with 10 incomplete decomposition searches and
20 incomplete architecture searches. These are separate measurements and do
not establish that recursion is the primary missing stage.

## Building-level frontier

Preserve every emitted candidate rejection, geometry identity, axes, available
end choices, precise issue/reason and reached stage. Compute inclusion-minimal
observed blocker sets per building across minimum and receiver families.
Report incomplete searches separately, including incomplete searches that
already have an embedded prefix. Such a prefix cannot be seeded.

An observed `{parallel}` set is a necessary opportunity at its stopping stage,
not a guarantee of rescue. Its later end, incidence or embedding requirements
have not been evaluated. Counts are building incidence, not assignment counts;
different minimal alternatives may be counted for the same building. Do not
sum them as disjoint buildings or call them sufficient repair sets. Later
counterfactual rescue requires the controlled experiments or a proved model.

Classify parallel contacts independently by transverse width equality,
longitudinal alignment/centering/offset, complete-side versus partial-side
contact, and same-Part versus inter-Part ownership. Retain per-building raw
counts and summarize building incidence.

The latest correction additionally requires producer-specific parallel-free
alternatives. For minimum and receiver families, record modeled assignments,
whether any declared contact arrangement avoids parallel, and that alternative's
maximum reached stage (including actual mesh success). `no_modeled_candidate`
is distinct from `parallel_unavoidable_in_modeled_family`. Incomplete families
cannot establish unavoidability. Contact kinds and Part grouping here refer to
the proposed architecture before end consumption, not nonexistent final roofs.
Measure receiver parallel-free alternatives where minimum has none; do not use
reject incidence to measure improvement. Recursive proposals remain a separate
diagnostic and must not be silently classified as absent in all possible models.

## Finite cover oracle

Select exactly 100 frozen inputs by boundary vertex count and stable corpus
order: the first 82 grid inputs with 6–14 vertices and all 18 nonuniform inputs
in that range. Selection is independent of generation outcomes. Enumerate all
contained rectangles in the footprint-boundary coordinate arrangement and all
nonoverlapping covers. A one-rectangle-per-occupied-box bound includes every
member count, rather than a hidden six-member limit.

Both axes enter the model domain. The pinned relation CSP may prune assignments
already impossible in the unchanged grammar. Every surviving assignment enters
global end/symmetry constraints, composition, GeometryProblem and embedding.
Count constructed graphs separately from embedded meshes. Cover and axis/end
budgets are explicit. Only completed zero-success searches establish failure
within this finite domain; arbitrary free-coordinate or nonrectangular models
are outside that statement. An incomplete input cannot support an impossibility
claim. Record its exact failed budget.

## Decision

If the complete oracle plus relaxed axes broadly constructs roofs while the
default discovery does not, retain the architecture and target the measured
discovery/domain barriers. If completed exhaustive cases still largely reject
at end/composition, stop incremental rectangle-junction expansion and compare
a whole-polygon gable topology prototype on the same failures. A censored
experiment requires completion or narrower stated conclusions, not a convenient
decision from successful prefixes.

The user now permits straight skeleton/global roof models as candidates for
that isolated comparison prototype after the gate. This supersedes the earlier
aggregation-only restriction for this comparison. A prototype must publish a
RoofGraph before the unchanged fixed GeometryProblem and solver. It cannot be
a runtime fallback, cannot let the solver infer topology, and cannot be promoted
to production from screenshot-only success. Independent coverage, planarity,
incidence and representative Blender inspection remain required.

## Current decision

The completed finite oracle and unchanged-grammar recursive comparison support
the isolated whole-polygon branch of this gate. In the same 100 small inputs,
recursive proposals have parallel-free assignments in every completed search
but still embed exactly the same six roofs as the cover oracle. The remaining
94 stop at ends or composition. Structured recursion adds no selectable input.
The full all-axis run remains incomplete and is not an impossibility proof.
See [the measured comparison and remaining limits](WHOLE_POLYGON_COMPARISON.md).
