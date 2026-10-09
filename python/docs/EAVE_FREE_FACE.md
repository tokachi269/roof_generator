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
- [Cells, Parts, end decisions and final features](authority/eave-free/equal_corner_T.svg)

The paired diagram compares seed 0 on `a99ad3b` and this repair. The earlier
revision could already generate the shared L option for this footprint; it
could not generate the resolved equal-width T option. The change adds that
interpretation to the valid set, so seed 0 now selects it. It does not establish
that one interpretation is aesthetically preferable to the other. A separate
transform check embedded 48 eave-free candidates across 24 rotated, reflected
and scaled inputs while preserving the graph.

This is an additional proven L/T interpretation. It does not solve the user's
staggered parallel-band footprint. The previous frozen-corpus measurements
belong to earlier production revisions. The fresh audit below measures this
repair separately and does not show broader footprint coverage.

The frozen branch corpus re-audit completed on this production source: 100/100
through RoofGraph, GeometryProblem, solve and mesh, and 100/100 actual installed
ZIP Blender conversions. This remains a separated-branch result, not general
orthogonal coverage. [Core report](authority/eave-free/branch.json),
[Blender report](authority/eave-free/blender-branch.json).

## Frozen corpus re-audit

The canonical and branch payload hashes match the earlier frozen inputs.
Every input still reaches partition and architecture in the orthogonal corpora.
Supported input counts and all 164 selected candidate IDs (64 canonical plus
100 branch) match the preceding offset-end-gate revision.

| Corpus | Inputs | Retained architecture candidates | Constructible topology candidates | RoofGraph / solve / mesh | Installed ZIP Blender | Unsupported / incomplete |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Grid stress | 1000 | 36196 | 4 | 3 | 3 | 980 / 17 |
| Nonuniform orthogonal | 150 | 5318 | 0 | 0 | 0 | 150 / 0 |
| Structured orthogonal | 103 | 1284 | 25 | 13 | 13 | 90 / 0 |
| Branch network | 100 | 300 | 100 | 100 | 100 | 0 / 0 |
| Convex quadrilateral | 48 | 48 | 96 | 48 | 48 | 0 / 0 |

Candidate totals differ from successful input totals. Blender attempts only
core mesh successes: nonuniform inputs were not attempted there. Grid's 17
incomplete searches are not counted as proven unsupported. Oblique 43 and
general-polygon 40 probes remain unsupported at partition, outside this repair.
This remains incomplete general orthogonal support.

[Core stages](authority/eave-free/coverage-eave-free.json),
[installed Blender stages](authority/eave-free/blender-coverage-eave-free.json),
[outcome classification](authority/eave-free/outcomes.json), and
[source/archive manifest](authority/eave-free/manifest.json) preserve this stage.

## Serial performance comparison

The starting revision's 20 core files were byte-compared with `0210d79`.
Its benchmark and the current benchmark ran serially after the coverage jobs
finished, with three samples, two warmups and a 24-building batch. No performance
rewrite or candidate pruning was introduced in this repair.

| Case | Starting core_total median ms | Current core_total median ms | Mesh before / after |
| --- | ---: | ---: | --- |
| U | 327.54 | 300.37 | True / True |
| Cross | 82.03 | 113.02 | True / True |
| Residential multi-reflex | 8.40 | 12.38 | False / False |
| Grid14 | 28.12 | 64.38 | False / False |
| Grid20 | 60.14 | 104.63 | False / False |
| Grid40 | 330.28 | 2293.13 | False / False |

Unsupported timings do not include successful embedding and must not be called
finished-mesh performance. The small sample describes this run; it does not
prove an optimization caused the U difference. Candidate evaluation and global
constraints remain costly. Raw measurements:
[before](authority/eave-free/mesh-performance-before.json),
[after](authority/eave-free/mesh-performance-eave-free.json).
The baseline raw `source_sha` is the enclosing checkout HEAD, not the extracted
code-root revision. The general audit likewise started before the production
commit; the manifest declares its actual production source and archive hash.

## Unresolved aggregation boundary

Current members still occupy whole minimum Cells and inherit their direction
domain. The shared/T constraint work does not supply arbitrary long-side region
ownership. The screenshot cases therefore remain ungenerated. Neither relation
provenance, a valid mesh, nor rejecting those inputs proves the requested natural
roof repair is complete.

The reviewed Laycock procedure supplies collecting guides from a skeleton
before roof-model assignment. After this stage was pushed at `587cf10`, the user
authorized Steps 1–5 as a diagnostic architectural aggregation guide, explicitly
excluding skeleton edges as final roof topology. The resulting
[13-input diagnostic](LAYCOCK_REGION_DIAGNOSTIC.md) demonstrates conditional
whole-Cell and splitting configurations. Growth and ownership remain unresolved;
production introduction and a natural-roof repair are not established. Existing
proof-backed operations remain unchanged.

The four screenshot approximations were also attempted with this installed ZIP.
All four remain unsupported at `inter_part_parallel`, with atomic scene failure.
[Actual operator report](authority/eave-free/user-images-operator.json).
This confirms that the new equal-width corner-T choice has not repaired their
long-side aggregation; it must not be advertised as the factory-roof fix.
