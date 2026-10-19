# Embedding roofs with fully declared face planes

## Current contract

Applies to packaged 1.5.0. Canonical polygon generation constructs
continuous PolygonRoof candidates, converts each to an indexed RoofGraph and
GeometryProblem, checks incident planes, embeds and validates every candidate,
then selects a completed roof by stable seed. The topology backend and candidate
authority are outside this solver change.

Each slope constraint declares a fixed eave origin `o`, inward unit direction
`n`, and pitch `p`. Its equation is

```text
-p*n.x*x - p*n.y*y + z = o.z - p*(n.x*o.x + n.y*o.y).
```

If every face has a declared plane, all face planarity constraints are linear.
Fixed boundary XY and fixed height anchors eliminate variables. Ridge direction
cross products are also linear and may couple vertices. The current per-vertex
`check_planes` is necessary feasibility only: it neither checks those coupled
ridge equations nor solves positions.

The Ren covariance objective is zero at every feasible solution of this fully
specified system. Nonlinear finite differences and repeated eigensolves do not
add information here. This is constrained embedding of an already decided graph,
not plane-envelope topology discovery or a new roof generator.

## Linear solution and remaining freedom

Solve `A*delta = b-A*x_initial` once with normalized rows and deterministic
partial-pivot elimination. Rank deficiency is not automatically a failure: a
vertex incident to two planes may slide along their intersection. Retain all
constraints, and select the feasible correction minimizing squared XY movement,
the existing displacement objective. Express the affine solution as `delta=q+B*t`
and minimize `||q_XY+B_XY*t||²` only in the remaining nullspace. No regularizer
changes a hard plane, anchor or direction equation.

For a complete plane contract covering every vertex, `B_XY` has full column rank:
a nullspace movement with zero XY has zero Z in each incident plane (Z coefficient
is one), hence zero movement everywhere. Thus that displacement minimum is unique.
Unused vertices or numerical rank failure are explicit unsupported problems.

Recheck original signed plane distances and ridge equations at the same normalized
tolerance as nonlinear solve, preserve fixed coordinates exactly, then invoke the
unchanged RoofMesh validator. Inconsistent equations and invalid projected mesh
fail; neither a nonlinear retry nor another seed repairs them.

Graphs without a complete declared plane contract retain the covariance optimizer
as their explicit numerical problem class. Selection by available constraints is
not failure fallback. The generic optimizer and historical planarity proofs remain.

## Evaluation

Historical comparisons and commands are in [the evaluation](../history/PLANE_EMBEDDING_EVALUATION.md).
