# Relation-to-topology support

## Scope and measurement

The primary result is a valid 2D RoofGraph and its GeometryProblem, not a solved
compound mesh. `audit_roof_support.py` records **every rejected assignment** and
all independent relation blockers in that assignment. Nonexclusive building
incidence, rejected-assignment incidence and relation occurrences have different
denominators. Downstream junction/embedding failures remain unobserved when a
relation blocks composition. A sole known blocker is only a conditional upper
bound on future support, never a prediction that removing it makes a roof valid.

The previous 833/1000 unsupported batch repeats six fixed outlines. A separate
corpus contains 1000 unique seeded connected-grid outlines, scaled to 3 metre
units. It is a synthetic coverage probe, not a housing-distribution estimate.
The same saved corpus is replayed before and after the operation change.

## Published mechanisms and applicability

| Relation | Published mechanism | Current indexed-graph consequence |
| --- | --- | --- |
| continuation | Hu/Fan/Noskov 2017 §3.4.1, Figs 12–13: eliminate triangular end caps at adjacent short ends | Specifies cap constraints, **not** the complete incidence for offset or stepped-width end contacts |
| terminal branch | Hu §3.4.3, Figs 15–18: shared corner junction or T combination; intersect all constraints imposed on an end. Laycock/Day 2003 §7 Fig 6 case 1: attached branch. Sugihara/Hayashi 2007 pp.312–313 Figs 4–6: narrow branches extend toward the wider receiving roof | Consume host near port and branch near cap; share ridge/valley/outer hip incidence; unequal width refines into two trivalent joints |
| multiple terminal branches | Sugihara Figs 5–6 demonstrate multiple branches on a main roof; Hu Fig 18 forbids choosing end combinations independently of other constraints | Recognize **all** ports first; permit replacements at distinct host ends only; rewrite host cycles once, not sequential pairwise merging |
| partial end | Hu end constraints do not specify arbitrary incomplete end/side incidence | Remains unsupported; a cap constraint alone is not a junction graph |
| parallel | Hu §3.3 rule 2 discourages adjacent long-side roof pairs to avoid narrow spaces | Partition ranking is available; this is not a published roof-connection template |
| interacting junctions | Kada/McKinley 2009 §2.4, Fig 11 replaces corner/T/cross blocks using compatible neighboring fitted roof parameters | Arbitrary overlap is not justified by footprint-only matching; existing equal-width opposite cross remains the restricted compatible case |

Primary sources were reread, including Hu §§3.3–3.5 and the original Sugihara
p.313 figure/text. Detailed source URLs and the earlier complete comparison are
in [ROOF_COMPOSITION_RESEARCH.md](ROOF_COMPOSITION_RESEARCH.md).

### Why continuation is not automatically a simple merge

If two nonoverlapping minimum rectangular cells have equal transverse bounds
and adjacent full ends, their union is one rectangle. Replacing them by that
rectangle preserves coverage and reduces the count, contradicting the minimum
certificate. Therefore aligned equal-width full-end continuation between such
cells cannot be the missing operation. The actual `continuation` vocabulary
includes offset and width-step end contacts. Hu's rule removes end triangles,
but does not determine their junction incidence. Implementing plain ridge
continuation for those contacts would claim support without a topology rule.
The audit separately checks this geometric distinction.

## Multi-terminal operation contract (before implementation)

This is a constrained **graph adaptation** of published branch extension and
shared corner incidence; neither paper supplies this exact indexed algorithm.
It reuses the existing proved single-terminal operation rather than claiming an
arbitrary new junction grammar.

1. Relations identify one receiver and distinct exterior-leaf branches, covering
   every member. All attachments are terminal, with perpendicular primitive axes.
2. Each consumed host end is distinct. The receiver is a geometric side role, not a global higher main roof.
   Each end uses the established single-terminal local wider/narrower
   refinement; either neighbor may be wider, independently of the other end. Mixed terminal/middle or two replacements on one end fail.
3. Allocate surviving exterior gable ports and a corner junction per attachment.
   Remove all consumed host ports, branch caps and artificial boundaries. Rewrite
   each host face using the full attachment set once; branch faces splice into
   that cycle. Equal-width joints have ridge/ridge/hip/valley incidence. Unequal
   joints split into high(host ridge/outer hip) and low(branch ridge/reflex valley)
   joined by a hip. The host ridge connects retained ports/joints once.
4. Distinct local replacements are disjoint cycle neighborhoods; each internal
   spoke has two opposite face incidences. Replacing a vertex by one vertex or
   a two-vertex path preserves disk links. The final RoofGraph validates links,
   one exterior boundary, Euler disk and complete exterior/member provenance.
5. Only after incidence is fixed, initialize XY along **declared primitive axes**.
   Internal-to-internal host ridge edges no longer require an exterior cap.
   Local high/low pairs may backtrack toward their axis intersection together;
   that coincident limit is never emitted. A crossing/degenerate drawing fails.
   No XYZ, plane envelope, Boolean, wavefront or optimizer selects incidence.
6. Primary tests supply independent planar metric witnesses for opposite-end
   attachments with narrower, equal and wider branches. Hu’s simultaneous end
   constraints do not justify a global wider-host restriction; Sugihara’s higher
   roof distinction is local to each connection. Keeping that distinction local
   is necessary for the existing slightly-wider-branch U fixture. Also verify input transforms, cyclic start, winding,
   collinear redundancy and relation-order permutations. Witness geometry is a
   test oracle, not production topology discovery or a fixture special case.

This operation does not imply interacting-junction, continuation, partial-end,
parallel-contact or arbitrary generated-grid support. It does not add a
nonlinear geometry solver or a Blender compound-mesh fallback.

## Baseline findings

See [canonical/support_before.json](canonical/support_before.json). The unknown
corpus has 2 supported, 986 unsupported and 12 incomplete-budget buildings.
Unsupported-building incidence: parallel 981, continuation 790, partial_end 790;
these counts overlap. All 284,324 continuation occurrences have width-step or
axis-offset bounds; zero are the trivial aligned full-end merge. Conditional
sole-known-blocker incidence is parallel 777, partial_end 61, continuation 38,
terminal arrangement 36. These upper bounds censor downstream failures.

The original U receiver is slightly narrower than both branches. A rule that
rejects this only because the geometric receiver is not the locally wider roof
would be more restrictive than the existing singleton terminal contract. The
multi-terminal extension must prove all local width orderings using independent
planar witnesses, while keeping distinct-end/leaf and noncrossing applicability.
