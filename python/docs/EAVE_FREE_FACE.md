# Equal-width corner-T: explicit slope support

The isolated L footprint `(0,0), (12,0), (12,4), (4,4), (4,10), (0,10)`
admits a selected corner-T end configuration. Its existing middle-junction
incidence has five faces, including one receiver slope without an incident
exterior eave. Before this repair the applicability gate rejected equal widths;
an isolated diagnostic of that incidence then reproduced GeometryProblem's
`pitched face lacks a declared exterior eave` error.

Composition now publishes the original member slope's exterior supporting line
as `RoofFace.support`. `eaves` still describes only physical incident edges.
RoofGraph validates that support belongs to the same member. GeometryProblem
requires a declared support and checks all incident eaves for collinearity;
it does not infer a support from adjacent faces. Optimization is unchanged.
The corner-T applicability gate allows an isolated equal-width branch as well
as a narrower branch; wider and multiple corner extensions remain unsupported.

`test_equal_corner_T_preserves_its_eave_free_face_through_embedding` fixes five
literal face cycles and independent analytic XYZ values at pitch 0.5. Missing
support and foreign-member support must fail. The resulting mesh must retain
the same graph object. This generalizes the embedding contract without changing
the topology to make the solver accept it.

Verification: 141 tests passed in 66.859 seconds; the support rejection test was
subsequently extended and its focused suite passed. The rebuilt ZIP matched
source. Blender 4.3.2 installed that ZIP in an isolated scripts directory and
ran 20 operator cases: 12 supported and eight unsupported with atomic failure.
The equal-width case produced five faces and preserved its graph through solve.
The actual operator report and camera render are saved below. These are camera
renders of Blender mesh output, not live viewport captures.

- [Installed operator report](authority/eave-free/operator.json)
- [Equal-width roof render](authority/eave-free/equal_corner_T.png)

This is an additional proven L/T interpretation. It does not solve the user's
staggered parallel-band footprint. The previous frozen-corpus measurements
belong to earlier production revisions; a fresh audit is running for this
repair and must be reported separately before making coverage claims.
