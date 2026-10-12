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

## Published mechanisms and their mapping

| Source | Actual mechanism | Implementation |
| --- | --- | --- |
| Held & Palfrader 2017, sections 3.1–3.2 and 4.1–4.3 | Source schedules, space-time surfaces, weakly z-monotone roofs with vertical facets, simultaneous non-elementary events | `sources.py` defines inclined and stationary source equations; `complex.py` separates inclined patches from walls. Permanent zero speed needs the explicit rules below; the paper's finite-delay premise is not claimed as a theorem for it. |
| Biedl et al., *Weighted straight skeletons in the plane*, sections 3–5 | Global front fragments and source identities; degeneracies depend on the speed domain | Active cyclic supports in `wavefront.py`. Only unit inward EAVE speed and zero GABLE speed are used. No negative weights or general weighted-roof guarantee is imported. |
| campskeleton, `HeightCollision.process`, `CoSitedCollision.findChains/processChains` | Gather coheight/co-sited contacts, discover all chains before mutation, remove collapsed chains, reconnect the surviving chains by angular order | Every current fragment is noded at the certified common time; coincident atomic intervals are resolved together; `rotation.py` constructs their planar cyclic link. The fixed 0.01 spatial grouping in the Java implementation is replaced by exact equality, not copied. |
| Huber & Held 2011, PSLG wavefront/motorcycle model | Global rather than shape-template processing of reflex and degenerate contacts | Vertex/fragment certificates include reflex contacts and components across the entire front. No motorcycle or native backend is called; the current implementation deliberately uses a small-input exhaustive certificate scan. |
| Surfer2, kinetic triangulation implementation | Native certified geometric state and event management | Inspected as a robustness reference. It is not a Blender runtime dependency: CGAL/native deployment and its exact zero-speed domain have not been validated here. |

No third-party algorithm source has been copied. campskeleton's Apache-2.0 Java
build needs a JVM; Surfer2 is GPLv3 with CGAL/C++ dependencies. The separately
inspected Python grassfire implementation uses MIT code but requires `tri`,
`geompreds` and `oseq`, and includes fixed near-zero/angle decisions. None is
presumed to satisfy this numeric contract without verification. The engine here
is GPL-3.0-or-later, matching repository licensing.

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

Development-only NumPy SVD and Shapely containment/intersection predicates
independently test planarity, footprint coverage and interior overlap. Containment
of each patch, pairwise disjoint interiors and equal total area imply coverage;
this avoids depending on one floating union overlay. A frozen step-wall case
demonstrates a raw GEOS union losing area despite those three checks and a
bounded-precision overlay agreeing. Raw union error stays in the diagnostic
record. No production coordinates are snapped for this test.
Those packages are not imported by the
kernel or its Blender script. The numerical oracle is evidence independent of
the contact rewrite; it is not a runtime fallback.

A floating-point mesh is a further representation gate. Exact vertices may be
unrepresentable or collapse at float precision. `MeshResolutionError` reports
that outcome instead of welding vertices or returning a partial mesh. Blender
has its own float representation; its smoke test checks the actual stored mesh.
Export conversion isolates a rounding interval, or resolves an adjacent-float
midpoint by exact comparison, before choosing a float. It does not assume a
fixed 128-bit interval midpoint is adequately rounded. Presentation time in a
stationary-remnant certificate uses physical units and is optional outside float
range; its exact radical quotient is always retained.

The fixed tests include an actual component split, two distinct contacts at the
same time, a six-source event, all 63 nonempty EAVE subsets on a concave L,
nonparallel full gables, exact rational rigid transforms, winding/cyclic changes,
collinear subdivision, limits, cache independence and numeric range failures.
All 63 L assignments yield 59 validated complexes, two negative-plane witnesses
and two scoped stationary-front certificates, with no kernel failure. Two distinct exact event times may round
to the same double and are still processed separately.

The frozen multi-corpus and mixed-role results, timings, SVGs and Blender evidence
are reported in [LINE_KERNEL_EVALUATION.md](LINE_KERNEL_EVALUATION.md). A successful
finite corpus does **not** prove universal completeness for every degenerate
simple polygon. The source/contact rules and postconditions are explicit, but
formal exhaustiveness/termination of the zero-speed contact model and a
sufficient independent admissibility criterion remain obligations before an
unconditional universal guarantee is advertised.

## Remaining gates

- Establish those universal zero-speed/completion obligations and automatic
  admitted intent generation, including an inclined-only architectural profile. A necessary plane check alone
  is not that policy.
- Transfer kernel authority into the addon and verify packaging/input transforms;
  the current standalone Blender script is not that integration.
- Define collinear partial transitions before accepting them.
- Implement actual Arc evolution/splice conventions, then general curves. Sampling
  straight chords is not a curve-source kernel.
- Continue performance work on the measured exact-predicate/noding costs.
  Existing nonlinear solve timings are not this kernel's construction budget.
