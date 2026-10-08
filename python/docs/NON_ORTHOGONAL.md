# Non-orthogonal input boundary

## Single convex quadrilateral

The rectangular minimum-partition theorem applies only to orthogonal polygons.
A convex four-sided polygon needs no decomposition: one geometric Cell, all four
original exterior sides, no cut, no adjacency, and no rectangular minimum-count
certificate. This input strategy joins the existing ArchitecturalPart and indexed
RoofGraph contracts. It is not an alternate generator or a failure fallback.

Ren 2021 §§4.1–4.2 accepts a fixed primal graph with arbitrary polygonal faces;
rectangle-only primitives in Hu 2017 §3.4 do not specify arbitrary quadrilaterals.
The additional primitive contract is therefore explicit: two opposite eaves at
one elevation, two gable ends, two planar slopes with the same declared pitch.
It is not attributed to Hu as a published quadrilateral junction operation.

For either opposite eave pair, signed perpendicular distances to the two eave
lines are positive inside a strictly convex quad. Their difference changes sign
across each gable side. Linear interpolation on that side gives one unique equal-
distance ridge port. Joining the two ports stays inside the convex polygon. The
result has two face cycles, one ridge and four split gable boundary segments.
This derives boundary ports from equal-pitch geometry, rather than choosing
midpoints for convenience. No plane envelope, Boolean or skeleton is used.
Nonparallel eaves produce a sloping ridge. Ridge direction is the canonical
geometric line between the declared ports, not orthogonal axis 0/1. Fix one ridge
height from pitch and eave distance; leave the other height variable. Covariance
optimization with explicit eave/pitch constraints solves that remaining height.
Both opposite-eave choices are valid architectural alternatives, retained for
stable seed selection. Flat/shed use the same single-cell contract. Hip remains
explicitly unsupported for a nonrectangular quad.

## Oblique compound probe

`oblique_L` has one reflex vertex and nonparallel left/right arm sides. Extending
its horizontal edge through the reflex corner to the opposite boundary can
produce two convex quadrilaterals. This is a visible geometric candidate, **not**
a minimum-quad partition certificate or an architectural recommendation.
The classical rectangle theorem and Hu's rectangle combination constraints do
not justify selecting that cut for arbitrary oblique compounds. Laycock 2003 §7
relies on rectilinear elementary regions and skeleton operations; its broader
skeleton route is outside this project's contract. Sugihara's width-extension
operation assumes rectangular parts. Kada's fitted junction blocks need roof
parameters/data beyond this footprint-only input. Ren solves supplied incidence,
not missing cell or junction decisions.

Thus the missing responsibilities are generalized quadrilateral decomposition,
nonperpendicular full-end/side attachment interpretation, and a proved angled
junction incidence with explicit slope/direction constraints. The current
orthogonal port recognizer checks rectangle caps/eaves; an oblique relation cannot
be fed through it by pretending 90 degrees. These probes remain partition-owned
unsupported; no rectification or silent fallback occurs. Affine/sheared fixtures
are combinatorial stress cases, not equal-pitch transformation oracles.
