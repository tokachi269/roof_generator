# Full-Line source wavefront

The implementation in `python/roof_kernel/` constructs concave as well as convex
full-Line complexes. It uses only the Python standard library. The distributed
1.5.0 addon is a separate release checkpoint; this kernel is not yet its default
input policy or packaged generator.

## Input and authority

```text
BoundaryPath + explicit RoofIntent
  -> exact source equations and necessary existence check
  -> global fragment/contact state
  -> common-time contact graph and cyclic links
  -> source patches with certified event coordinates
  -> validated RoofComplex
  -> indexed mesh view
  -> Blender
```

Inputs are finite rational coordinates (including the exact rational values of
Python floats), a simple hole-free polygon, and full geometric-edge EAVE/GABLE
roles. Winding and world axes are unrestricted. A redundant collinear vertex
with the same role retains provenance but does not create a new roof source.
An EAVE/GABLE transition inside one straight geometric edge needs a partial
boundary model and is not accepted by this domain. Arc, Curve, holes, touching
paths, negative speeds and independently varying pitches are outside it.

Caller-supplied Line IDs own provenance. `Plane` is a source equation, not a
fitted plane or a roof primitive. `RoofComplex` owns vertices, time clusters,
inclined patches and stationary patches. There is no rectangle/cell geometry in
the constructor. Architectural analysis can supply intent later; no architectural
intention is inferred or silently changed here.

With a rational normal `n`, normalized by its largest absolute component, a
source has the local equation

```
n dot u = c + s * tau
s(EAVE) = sqrt(n dot n)
s(GABLE) = 0
world XY = origin + scale * u
world time = scale * tau
Z = eave_height + pitch * world_time
```

The scale is an exact power of two. Adjacent supports give affine vertex
trajectories. A vertex/contact time is a quotient of rational sums of square
roots. Positions are evaluated from these equations; neither an embedding
optimizer nor plane-envelope topology discovery participates.

Published mechanisms, inspected implementations and license/adaptation limits
are recorded in [kernel research](../research/KERNEL_RESEARCH.md).

## Contact operation

The state is a collection of oriented source-fragment cycles. For every current
vertex, test contacts with every current fragment, and choose the earliest
future time by certified comparison. A first change in a straight fragment front
is witnessed by such a vertex/fragment contact, including a segment collapse.
The implementation does not maintain separate collapse, split, gable/reflex or
high-valence handlers.

At that time:

1. Register all evaluated endpoints. Equal position **and time** means one node;
   different locations at the same time remain distinct contacts.
2. Node every fragment against every contact lying on it and within its interval.
3. Cancel opposing coincident atomic intervals. For equally oriented intervals,
   the faster inward support survives; identical-speed/source geometry combines
   lineage only. This is the local half-plane rule: immediately after contact,
   equal oriented normals impose the larger inward offset. No invented plane is
   inserted.
4. Pair surviving directed fragments by their planar cyclic link: the first
   outgoing ray clockwise from the reverse incoming ray bounds the surviving
   material on its left. Verify the pairing is bijective.
5. Enumerate positive oriented bounded cycles, retire collapsed contours and
   coalesce consecutive coincident parallel supports with the same dominance
   rule.
6. Node and link again at **the same time** until the cyclic support state is
   unchanged. No zero-time strip is emitted. The work budget also applies to
   this fixed-point closure.

Swept strips between successive times are oriented pieces of their declared
source equations. Only strips adjacent through a common edge on the same
physical source plane are merged. Disconnected collinear source regions do not
acquire each other's provenance. Source-patch extraction uses the same cyclic
link, in XY for an EAVE and in `(along source, time)` for a GABLE.

Degree-two section vertices are removed only after proving they and both
neighbors lie on the same two independent planes (or on one source plane and
`t=0`). Both incident patch cycles change together. Coordinates and genuine
junctions stay unchanged; event/contact records are retained. This suppresses
subdivision artifacts without a floating-point weld, triangulation or repair.

## Numeric certificates

`precision.py` keeps `Surd` sums of square roots and `Scalar` quotients. Radical
terms in the same rational square class are combined using exact integer square
roots. Distinct square classes are linearly independent over the rationals, so
exact zero is recognized algebraically before any sign isolation.

For a nonzero sign, certified double intervals are tried first. Square-root
bounds are checked by squaring their exact float-to-rational values. Conversion,
product and sum bounds are rounded outward. Uncertain signs use rational
square-root intervals at 64, 128, 256, ... bits. Precision exhaustion is an
incomplete execution, not unsupported geometry. No fixed spatial/time epsilon,
angle snap, jitter or approximate equality decides contact incidence.

Patch-edge tangents come from their incident source equations. Orientation
predicates use these fixed tangents instead of unnecessarily multiplying
coordinates from three unrelated event times. All decisions still use the same
certified arithmetic.

Memoized trajectories, contact equations, evaluated endpoints, fragment intervals
and noding results live in one construction. They are immutable calculations;
no global cache or incidental identity affects source IDs. Cache-disabled
construction produces the same inspected complex.

## Existence and surface profile

A necessary preflight condition is that every interior location have at least
one nonnegative EAVE source height. Exact triangulation/half-plane clipping is
used **only** to find a violated witness, not to discover roof topology. Failure
returns rational coordinates and signed source equations. Passing this condition
is not a sufficient-admissibility theorem.

If propagation leaves a positive-area component bounded entirely by stationary
sources and no moving fragment remains, that component cannot disappear in
finite time in this model. Its exact rational polygon is returned as a
`stationary_remaining_front` certificate. This certificate concerns the specified
boundary-evolution model; it does not assert that every imaginable building roof
with additional sources is impossible. An all-GABLE assignment has its own
`no_moving_source` certificate.

Some legal mixed roles require **internal vertical step patches**. For the L
boundary `(0,0),(8,0),(8,3),(3,3),(3,8),(0,8)`, EAVEs 2 and 5 give planes
`time = 3-y` and `time = x`. The stationary `x=3` source produces a vertical
connection where the plane heights differ. This is a weakly z-monotone complex,
not a continuous inclined-only roof graph.

`mesh.view(include_walls=True)` preserves the complete complex. The inclined-only
view omits stationary walls **only** after certifying their full projected
intervals lie on the original exterior boundary. It raises `WallRequired` when
an internal wall would be lost. This export-profile distinction is not kernel
nonexistence and is not repaired in Blender. Automatic intent selection must
account for the desired architectural profile before addon adoption.

## Validation and proofs

The kernel validates source equations and nonnegative time, complete simple
patch cycles with positive area in their own planar coordinates, opposing shared
edge orientation, edge and vertex-link manifoldness, connected faces, Euler disk,
one base boundary and exact coverage of every original source interval. Tangents
and nonadjacent-segment predicates certify patch simplicity without a generic
polygon Boolean library. Positive inclined projection and the base boundary give
projection degree one; stationary patches have zero projected area.

Independent oracle methods and frozen cases belong to
[the evaluation](../history/LINE_KERNEL_EVALUATION.md), not the runtime dependency contract.

A floating-point mesh is a further representation gate. Exact vertices may be
unrepresentable or collapse at float precision. `MeshResolutionError` reports
that outcome instead of welding vertices or returning a partial mesh. Blender
has its own float representation; its smoke test checks the actual stored mesh.
Export conversion isolates a rounding interval, or resolves an adjacent-float
midpoint by exact comparison, before choosing a float. It does not assume a
fixed 128-bit interval midpoint is adequately rounded. Presentation time in a
stationary-remnant certificate uses physical units and is optional outside float
range; its exact radical quotient is always retained.

## Evaluation and outstanding obligations

Finite corpus outcomes, timings and installed Blender observations are in
[the evaluation](../history/LINE_KERNEL_EVALUATION.md). The
[kernel contract](ROOF_KERNEL_CONTRACT.md#adoption-and-extension-gates) owns the
current adoption/extension gates. This implementation does not claim a universal
completeness theorem, an automatic architectural intent policy or addon integration.
