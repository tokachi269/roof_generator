# Fixed-topology embedding

## Published objective and implementation boundary

Ren et al., *Roof Modeling from Satellite Images*, ACM TOG 40(6), 2021,
[preprint §§4.1–4.2, equations 1–2](https://arxiv.org/abs/2109.07683),
define `E = sum_f smallest_eigenvalue(Cov(X_f))`. The covariance has divisor
`|f|-1`. It is zero for a planar face. Equation 2 adds a squared Frobenius
XY displacement term and fixes a roof height to avoid the all-flat minimizer.
The optimizer accepts primal incidence; it does not infer or change topology.

The historical repository implementation (`python/core/roof_core.py` before
`ea2687a`) used NumPy covariance/eigenvalues, finite differences and SciPy BFGS.
Its XY term was an **unsquared** norm, unlike equation 2. The original [MATLAB implementation](https://github.com/llorz/SGA21_roofOptimization/blob/main/RoofOptimization/utils/construct_3D_roof_from_roof_graph.m) likewise uses covariance eigenvalues, an unsquared norm and `fminunc` quasi-Newton optimization with 1e-12 tolerances and fixed height indices. This implementation
uses the equation's squared term. No historical source is restored or copied.

## Contract

`GeometryProblem` owns initial XYZ, fixed boundary XY (all indices outside
`variable_xy`), free internal XY, free Z, explicit fixed Z anchors, face cycles,
and declared ridge direction constraints. Direction constraints are homogeneous
linear cross products; eliminating these constraints leaves only permissible
optimization coordinates. Neither plane intersections nor an envelope chooses
coordinates or incidence. Each slope contributes orthogonal residuals to its
best-fit covariance plane, divided by `sqrt(|f|-1)`; their squared sum is exactly
the published covariance objective. A deterministic symmetric 3×3 Jacobi
iteration supplies the eigenvector. Levenberg–Marquardt solves the small nonlinear
least-squares problem using finite-difference residual derivatives. This is a
standard numerical optimizer, replacing dependency on SciPy, not the roof energy.

Initialization is the supplied graph drawing plus explicit height anchors.
All unconstrained internal heights start at the largest anchor, as in the
paper's constant roof-height initialization. Declared primitive anchors can be
more numerous than the single anchor in equation 2: they retain the requested
pitch and existing geometry contract, including a receiver whose caps were
consumed. The solver never decides an anchor or an architectural relation.

XY displacement regularization starts at `1e-4`, then decreases to `1e-8` and
zero. This explicit continuation prioritizes proximity while obtaining the
strict planar mesh contract: a permanently positive soft regularizer need not
produce zero planarity. Failure to attain planarity is reported, not repaired.
Stopping requires maximum point-to-best-fit-plane distance below the configured
perimeter-normalized tolerance and ridge direction residual below tolerance.
Iteration exhaustion, nonfinite objective, contradictory constraints and an
invalid final embedding are explicit solve failures. Optimization success is
separate from mesh validation (positive projection, fixed boundary, noncrossing,
shared incidence, consistently upward normals). The mesh consumes exactly the
original face cycles. No triangulation, topology rewrite or fallback occurs.

Flat and individual rectangular primitives have exact analytic embeddings.
Choosing that solver from the known primitive contract is not a fallback after
optimization failure. Compound pitched graphs use the nonlinear solver.

## Explicit pitch constraint

The uncapped receiver test exposed a genuine missing constraint: height anchors
alone permit a planar receiver whose ridge slides transversely and changes its
pitch. `GeometryProblem.slope_constraints` now declares `(face, inward eave
normal, pitch)`. The equation `dot(face_normal.xy, inward) + pitch*normal.z = 0`
retains the requested slope. It is an additional user constraint of the kind
allowed by Ren §4.2, not a replacement roof energy. A 0.1 perimeter-unit residual
scale makes the dimensionless normal equation commensurate with distance
residuals; **acceptance checks the unweighted equation independently**. Tests
compare solved vertices against independently authored equal-pitch witnesses.

The stored slope constraint also includes its fixed exterior eave XYZ origin.
At a planar solution the normal equation above is equivalent to all face
vertices satisfying `z-z_eave = pitch*dot(xy-xy_eave,inward)`. The optimizer uses
these continuous signed-distance residuals alongside the covariance energy;
this avoids a discontinuous best-fit normal at a nonplanar intermediate iterate.
No plane-plane intersection is computed. The eave origin, inward direction and
pitch are supplied explicitly by GeometryProblem, never guessed inside solve.
