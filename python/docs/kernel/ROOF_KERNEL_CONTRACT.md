# Boundary-conditioned roof kernel

Status: full-Line source-wavefront implementation with certified arithmetic,
concave mixed-role construction and independent mesh proofs. The distributed
1.5.0 generator remains the checkpoint. The current implementation, wall-profile
distinction and remaining universal/migration obligations are in
[LINE_KERNEL_IMPLEMENTATION.md](LINE_KERNEL_IMPLEMENTATION.md). Finite corpus
success is not an unconditional completeness theorem or an addon promotion.

## Objective and authority

```text
closed source-labelled BoundaryPath
  -> explicit EAVE / GABLE intervals (RoofIntent)
  -> one global boundary-conditioned wavefront
  -> RoofComplex with event coordinates, times and source patches
  -> validation
  -> mesh discretization
  -> Blender
```

Rectangle, receiver and symmetry analysis may suggest intent. They must not decide
whether the kernel can construct a roof. A gable is declared before propagation;
it is not a triangular face discovered in an ordinary skeleton. There is no
terminal, parallel-support or shape-name predicate in the target kernel domain.
An ordinary all-eave skeleton is one instance of this model, not a fallback for a
failed gable request. No new cap/junction exceptions will be added to 1.5.0 as part
of this work.

## Necessary existence condition and proved convex domain

A simple footprint with at least one eave is **not** enough to guarantee the
requested roof under the proposed constant-pitch, no-additional-source model.

Use the CCW polygon

```text
(0,0), (8,0), (8,3), (3,3), (3,8), (0,8).
```

Declare only edge 3, `(3,3) -> (3,8)`, an eave, with all other edges gables.
This is a valid simple straight footprint. Its sole inward eave normal is
`(-1,0)`. With unit run-time and pitch `p > 0`, every inclined patch must lie on

```text
z = h + p * (3 - x).
```

The interior point `(6,1)` would have height `h - 3*p`. Thus a terrain covering
the footprint, staying above the common eave height, made only from this source
plane cannot exist. Vertical gable walls cannot cover an open projected region.
More event handlers, a seed or a nonlinear solve cannot correct this contradiction.
Introducing another source or changing the intent would change the input model.

For any input, a necessary condition is that the union of the nonnegative inward
half-planes of the declared eaves covers the footprint interior. This is only a
necessary test; it is not asserted to certify global wavefront completion. A
kernel implementation must not call every case that it cannot solve "invalid
intent". It needs a mathematical impossibility witness to make that diagnosis.

For a bounded convex straight polygon, at least one full-edge eave **is** sufficient:
all inward distances are nonnegative throughout the polygon. If `E` is the set of
eaves, its remaining wavefront region is

```text
W(t) = P intersect { d_e(x) >= t for all e in E }.
H(x) = min { d_e(x) : e in E }.
z(x) = h + p * H(x).
```

The regions are nested and disappear in finite time. The height is continuous,
nonnegative and piecewise affine. Each projected patch has an eave source. This
is a useful independent closed-form proof domain; it is **not** a formula for
concave straight skeletons and must not be extended to them by a plane envelope.

An all-eave simple straight polygon has the classical inward-wavefront definition.
The current bundled implementation's event exception is an implementation failure
on that domain, not proof that the roof does not exist.

## Boundary and intent representation

BoundaryPath owns an ordered closed path of source primitives. Initially the
implemented geometric primitive is Line. The contract reserves CircularArc and
parametric Curve as different geometric sources, without pretending they can
already be propagated by the line engine.

Each source has a stable caller-supplied identity and its own parameter range.
RoofIntent partitions that range into disjoint, covering EAVE/GABLE intervals.
Splitting an interval for predicates or mesh sampling retains its source identity
and parameters. Incidental sample or vertex numbering is not an architectural ID.
Winding reversal reverses the interval parameters and physical inward normals.
Collinear vertices with the same role may be computationally coalesced; a role
transition must never be erased by polygon normalization.

Full-edge intent is the first proof input. A collinear EAVE/GABLE transition has
adjacent supports with different speeds: their offset lines separate immediately
and have no intersection. The model must specify the connector/boundary evolution
at time zero before accepting arbitrary partial intervals. A guessed tiny edge,
coordinate perturbation or undeclared source plane is not that specification.
This is a missing model decision, not a reason to quietly map partial intent to
a whole-edge gable. Arc and Curve roles also retain exact parameter intervals.

## Kinematics and RoofComplex

Normalize units once and retain the inverse physical frame. For a CCW Line source
with inward unit normal `n` and `c = dot(n, a)`, its active support is

```text
dot(n, x(t)) = c + speed * t
speed(EAVE) = 1
speed(GABLE) = 0
z(t) = eave_height + pitch * t
```

The inclined patch of an eave therefore has the exact equation
`z = eave_height + pitch * (dot(n,x) - c)`. A gable contributes boundary/wall
incidence, not an inclined roof patch. Adjacent support equations determine
vertex trajectories where their intersection is defined. The kernel records
those trajectories and collision times; it does not seek coordinates with a
generic nonlinear optimizer after deciding topology.

RoofComplex is the authority for:

- vertices with spatial position and event time;
- oriented patch boundaries and source primitive/interval identity;
- shared crease incidence and boundary traces;
- event clusters, with all participating active fragments;
- separate wall patches, where the boundary evolution generates them.

For Line eaves, roof patches are planar. RoofGraph is a validated indexed planar
view of that complex, with the same shared vertices and patch incidence. Walls
are not inserted as positive-projection RoofFaces. Curve patches eventually have
their own surface evaluation and error-bounded tessellation, rather than acquiring
one semantic roof face per sampled chord. Mesh conversion may not repair topology,
invent faces, replace intent or alter a source patch to make a validator pass.

## Events and numeric contract

The kernel needs active fragments with source lineage and oriented adjacency, not
a list of independently generated building parts. Edge collapse, reflex contact,
coincident endpoints and collinear overlap are changes to this one state.

1. Predict certificates for the current state and find the earliest event time.
2. Resolve overlapping time uncertainty before deciding which events coincide.
3. Collect the entire time cluster. Distinct spatial contacts at that time remain
   distinct components inside the cluster.
4. Build the contact incidence before changing any participant. Resolve affected
   components together, including zero-time events exposed by that change.
5. Finalize swept patches; invalidate old certificates; continue only with a
   closed, correctly oriented front. A collapsed segment is a ridge trace, not
   a surviving zero-area polygon.

The current full-Line implementation nodes and reconnects common-time fragments
by exact cyclic links; see [implementation](LINE_KERNEL_IMPLEMENTATION.md).
This explicit rule and finite validation do not by themselves prove universal
zero-speed exhaustiveness or termination. Kinetic triangulation is a researched
alternative state/certificate mechanism, not a current runtime dependency.
Candidate priority or dictionary order must not choose an arbitrary post-event
pairing. Shared events are not split into fixture-specific templates.

Filtered floating-point predicates need a precision escalation path for uncertain
signs/times. With Euclidean unit normals even rational line input leads to square
roots; using Fraction only for the original coordinates does not make all event
predicates exact. No blanket epsilon merge, snapping a real angle, or perturbing
the footprint establishes robustness. Resource limits and cancellation are
separate execution outcomes. A bounded prefix is never a completed RoofComplex.

## Failure ownership

| Outcome | Evidence required | Interpretation |
| --- | --- | --- |
| Invalid boundary | self-intersection/touching, zero area/length, nonfinite geometry, broken primitive continuity | Input error |
| Inconsistent intent | incomplete/overlapping intervals or a proved nonexistence witness | Input/model error |
| Unspecified model | partial-transition/curve rule not yet defined | Development scope; do not claim the universal contract implemented |
| Kernel failure | valid admitted input, unresolved event or failed complex invariant | Bug/incomplete implementation, never normal UnsupportedRoofError |
| Incomplete execution | work/memory/precision limit or cancellation | Execution outcome; no mesh prefix |

The target guarantee is: **every mathematically admissible input in the published
kernel domain produces a validated complex, unless execution is incomplete**.
This domain cannot be defined as "whatever the current backend succeeds on".
Automatic intent generation must produce admitted intents by construction, or
expose the model ambiguity; it cannot silently substitute all-eave hip.

## Current implementation boundary

`python/roof_kernel/` constructs full-Line, simple hole-free boundaries with
explicit full geometric-edge EAVE/GABLE roles, including concave paths and
nonparallel supports. Source identities and redundant same-role collinear
vertices retain provenance. Partial collinear role transitions, Arc/Curve, holes,
negative speeds and independently varying pitches are not admitted model inputs.
Exact radical arithmetic, common-time contact closure, source-patch extraction,
complex validation and certified float export are implemented. No rectangle
primitive, ordinary-skeleton cap rewrite or embedding optimizer is called.

Internal stationary patches can be necessary. A validated wall-inclusive complex
is not necessarily a continuous inclined-only roof: `mesh.view()` raises
`WallRequired` rather than discard an internal wall. Float export can separately
raise `MeshResolutionError`. Neither is a nonexistence proof. Necessary negative
plane witnesses and stationary-remnant certificates have the scoped meanings
explained in [the implementation](LINE_KERNEL_IMPLEMENTATION.md).

## Adoption and extension gates

| Next obligation | Completion evidence required |
| --- | --- |
| Universal full-Line claim | A sufficient independent admissibility criterion and zero-speed contact exhaustiveness/termination argument; finite successful corpora alone do not suffice. |
| Automatic architectural intent | Produce admitted intents or expose ambiguity, with an explicit inclined-only versus wall-inclusive profile; never substitute hip after gable failure. |
| Addon authority transfer | One declared canonical route, input/frame/provenance and failure mapping, installed ZIP/Blender and packaging proof; standalone mesh export is not integration. |
| Partial EAVE/GABLE transitions | Define the time-zero connector/evolution rule before implementation and independent proofs. |
| Arc, then general curves | Define actual offset/contact/splice evolution and curved-surface approximation/error contracts; sampled line chords are not that kernel. |
| Performance | Measure construction, predicates/noding, validation and export separately with unchanged complex signatures; no unmeasured latency claim. |

The packaged addon remains 1.5.0 until the adoption gates are met. SGA21 remains
an independent graph-editing capability; do not remove its optimizer merely
because this constructor derives event coordinates directly.

[Implementation](LINE_KERNEL_IMPLEMENTATION.md) owns algorithm and numeric detail.
[Full-Line evaluation](../history/LINE_KERNEL_EVALUATION.md) owns measured corpus/Blender
results. [Initial convex proof](../history/KERNEL_CONVEX_PROOF.md) and
[source research](../research/KERNEL_RESEARCH.md) retain the earlier evidence and
rationale without constraining the current implementation to the convex oracle.
