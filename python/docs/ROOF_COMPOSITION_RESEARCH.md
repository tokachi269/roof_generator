# Published roof-part composition reassessment

Starting implementation: `ac1ff8b6b8387aab92e91801d12c9eafad3ed19c`.
This note precedes algorithm changes. The classical minimum rectangular
partition remains unchanged. A cell is an analysis region, not a promise of
one final roof; an artificial interval is not a roof edge.

## Sources actually reread

- **Laycock & Day (2003), Automatically Generating Roof Models from Building
  Footprints**, [full paper](https://www.sthu.org/misc/SKRW14/papers/LaycockDay_2003_AutomaticallyGeneratingRoofModelsBuildingFootprints.pdf),
  Section 7, six-step procedure, Figures 4–6 on PDF pp. 3–4. The local full PDF
  was read, including the merge drawings, despite a web-reader fetch error.
- **Kada & McKinley (2009)**,
  [full paper](https://www.isprs.org/proceedings/xxxviii/3-w4/pub/CMRT09_47.pdf),
  Sections 2.2–2.4, Figures 9–11, printed pp. 49–51. Both text and junction
  diagrams were read. The neighbor replacement rule is specifically Section 2.4.
- **Sugihara & Hayashi (2006)**,
  [full paper](https://www.jstage.jst.go.jp/article/journalac2003/15/0/15_0_67/_pdf),
  Sections 3–4, printed pp. 69–73, Figures 8–11. The Japanese text was read.
- **Sugihara & Hayashi (2007)**,
  [full paper](https://www.jstage.jst.go.jp/article/journalac2003/16/0/16_0_309/_pdf),
  Section 4(2), printed pp. 312–313, Figures 4–6, plus the CG workflow on p. 311.
- **Sugihara & Kikata (2013), Automatic Generation of 3D Building Models from
  Complicated Building Polygons**,
  [author-hosted full paper](https://researchmap.jp/sugihara1128/published_papers/14649928/attachment_file.pdf),
  DOI `10.1061/(ASCE)CP.1943-5487.0000192`, partitioning scheme/process,
  printed pp. 479–480, Figure 3. Additional investigation confirms extension
  of a partitioned rectangle toward a wider/higher main roof. It explicitly
  distinguishes the earlier fat-rectangle scheme from the later branch scheme.
  The paper was published in 2013, despite earlier online dates/search labels.
- **Ren et al. (2021)**,
  [full preprint](https://arxiv.org/pdf/2109.07683), Sections 3.1–3.2, 4.2–4.3,
  and initialization at the end of Section 4.3. Primal face cycles or dual face adjacency
  precede the geometry solve; outline information alone does not uniquely
  identify a real roof. Learned topology generation is a separate application.

These are algorithm references, not incorporated source code or redistributed
paper figures. New inspection drawings will be generated from this repository's
own inputs and graph records.

## What happens after decomposition

| Source | Input decomposition | Primitive | Connection/Junction | Main/branch decision | Ridge/Valley/Hip result | Current Graph mapping |
| --- | --- | --- | --- | --- | --- | --- |
| Laycock & Day, Section 7 | Reflex rays create elementary rectangles; skeleton lines grow axis-aligned rectangles; collect elementary regions, set difference and union into larger exterior boundaries before roofing. | Section 6 roof styles assigned to the aggregated boundaries, not indiscriminately to every elementary rectangle. | Figure 6 case 1 attaches a side branch; the drawing extends the branch roof inside the receiving region. Case 2 merges models with two collinear exterior edges. | Skeleton-grown regions determine larger roof units; no independent largest-area/main score is specified. | Case 1 shows two slanted connector edges meeting the branch center line inside the receiving roof; case 2 removes a redundant join between continued exterior edges. General cycle rewriting/overlap scheduling is not specified. | Keep Cell adjacency; recognize a full branch end attached to a host side, consume the internal cap, splice two branch slope cycles into the host slope. Same-axis continuation is a separate candidate, not an artificial-edge crease. Do not transplant its skeleton backend. |
| Sugihara & Hayashi 2006, Sections 3–4 | RL branch extraction; prefer rectangles nearer a square; iterate until the body has four vertices. | Rectangular roof/building parts constructed and placed by the CG module. | CSG primitive construction/placement is described; an explicit narrow-to-wide junction algorithm is not given here. | Fat-rectangle selection belongs to partitioning. | Figures 9–10 show combined buildings, without an indexed junction rule. | Do not cite this year as the source of a narrow/wide connection rule; preserve minimum partition instead of resurrecting its greedy partition. |
| Sugihara & Hayashi 2007, pp. 312–313 | Cut off a rectangle with a short DL; DL length must be below receiving main-roof width; recalculate RL data after removal. | Rectangular roofs placed by CSG. | Extend a narrower/lower branch toward a wider/higher main, Figure 5; multiple branches shown in Figures 5–6. | Branch width is DL length. With shared slope, greater transverse width implies the higher main roof. Branch/receiver is a local attachment relation, not a global largest-cell heuristic. | The low branch enters a main slope; its internal end is consumed. The drawings motivate termination and two valleys. Mesh union details and interacting junction rules are not specified. | Use the width relation and attachment ports to select a junction before solving heights. Retain host ridge; insert a branch-termination vertex and two reflex-corner valley edges. This topology extraction is our explicit adaptation of the published extension, not a claimed verbatim face-loop algorithm. |
| Sugihara & Kikata 2013, pp. 479–480 | Same narrower-branch scheme; warns the earlier fat-rectangle scheme did not always yield plausible roofs. | Rectangular parts, including gable/hip and variants; CG builds parts/roof boards. | Explicitly extends the partitioned rectangle toward a wider/higher main roof. | Shared slope and narrow-to-wide relation, inherited from the branch extraction. | Confirms the extension mechanism, but gives no complete arbitrary junction interaction table. | Confirms the above graph interpretation. Do not use its inner-contour straight skeleton or CSG as this route's topology backend. |
| Kada & McKinley, Sections 2.2–2.4 | Generalized quadrilateral cells, with approximate outline changes; different from minimum partition. | Fit flat/shed/gable/hip/Berliner primitives and corner/T/cross connecting blocks using local LiDAR normals. | After fitting, reexamine cells with neighbors on consecutive sides or at least three sides; choose compatible connecting shape joining the most neighbors, using their types, parameters and arrangement. | Neighbor roof fits supply direction/type/height; footprint alone does not replace these measurements. | Figure 11 has straight gable, corner, T and cross face-incidence patterns; the junction cell is replaced, not capped as an independent gable. Hip uses equal slopes during fitting. | Reconsider junction templates as incidence operations driven by ports. An isolated middle branch at equal widths can use the T incidence pattern. Recognize all relevant adjacencies before edits. Do not pretend LiDAR-free minimum cells automatically give its fitted junction blocks. |
| Ren et al., Sections 3–4 | No minimum rectangle partition algorithm. | Roof graph with outline/interior vertices and oriented face cycles; optional dual graph. | Authored/learned adjacency establishes topology first; optimizer embeds that fixed incidence. | User/topology generator must decide. | Planarity solve realizes specified roof edges; it does not choose branch/host or junction class. | Supply our authoritative RoofGraph faces/edge meanings and fixed boundary. XY seeds are disposable; no final XYZ or plane envelope is needed to select incidence. |

The original papers do **not** collectively specify a complete, deterministic
footprint-only graph grammar for arbitrary minimum partitions. That absence
must remain visible rather than be filled with a claimed published algorithm.

## Reevaluate previous decisions

`ROOF_GENERATOR_DESIGN.md` rejected Kada corner/T/cross junction classes along
with LiDAR fitting and generalized footprints. It adopted supporting-edge planes
from Laycock and reflex/aspect ideas from Sugihara, then solved connections by
plane overlay. This documents what was selected, but does not establish why
the published junction operations themselves were unsuitable. The old scope
favored oblique quads and one plane-based connector, and excluded their fitting,
skeleton/rectilinear, RL and CSG machinery. These are recorded constraints, not
evidence that junction incidence should have been discarded.

Withdraw the blanket rejection of junction operations. Keep the rejection of
outline rectification, LiDAR as a required input, wavefront and Boolean backends
for this evaluation. Separate those backends from their reusable incidence rules.
The initial `GRAPH_FIRST_DESIGN.md` terminal graft is a useful prototype, but
its unequal-width refinement was not adequately tied to the narrow/wide source;
this note makes the adaptation and its common-slope/eave assumption explicit.
No historical reason beyond the recorded designs is invented.

## Case matrix and adoption categories

**A**: transfer a published incidence/template directly. **B**: transfer the
topology effect of a published geometric/CSG extension. **C**: combine existing
rules with explicit ownership boundaries. **D**: not covered by surveyed method
at the precision required for this Graph contract; additional evidence/inputs
are needed before an implementation, not permission to silently guess.

| Relation to inspect (fixture names are not predicates) | Published mechanism | Category / current applicability |
| --- | --- | --- |
| Terminal side attachment | Laycock Fig. 6 case 1; Sugihara narrow/wide extension; Kada corner pattern | B/C: full branch gable end on a partial host eave, one shared endpoint at a host corner; preserve existing terminal graft and its independent embedding witness. |
| Middle side attachment | Sugihara Fig. 5 interior branches/extension; Kada T pattern | B/C: full branch end strictly inside a host side. Narrow branch terminates on a slope with two valleys; at equal width use the T incidence with the termination on the host ridge (A). |
| Two branches / U | Sugihara multiple branches; Kada neighboring junction replacement | C in compatible port arrangements; not a U rule. Two terminal replacements on the same receiver, or a minimum partition whose receiver is narrower, are not yet proved. |
| Cross | Kada Fig. 11 cross connecting block | A candidate if four fitted compatible ports identify one junction region. A three-cell minimum cross partition is not by itself that fitted block. Simultaneous opposite equal-width attachments need a shared cross template, not two coincident T vertices. |
| Multiple branches | Sugihara Figs. 5–6; Kada neighbor reassessment before replacement | C: collect relations for the whole adjacency graph first. Disjoint narrower middle insertions into one host slope have separate boundary intervals and commute. Intersecting branch extensions are D at the needed contract precision. |
| Unequal widths | Sugihara 2007 p. 313; 2013 pp. 479–480 | B: use transverse widths with common slope/eaves; narrower ridge remains below main ridge. Unequal pitch/eave levels can change incidence and require architectural input. |
| Same-axis continuation | Laycock Fig. 6 case 2 | A/B candidate: suppress internal cap and continue ridge for compatible aligned parts. Arbitrary offsets/width changes lack a complete indexed rule in the surveyed text. Not automatically a side-branch operation. |
| Perpendicular branch | Laycock case 1; Sugihara extension; Kada corner/T ports | B/C: the consumed branch end determines a perpendicular ridge; the receiving side remains a host slope. |
| Several adjacent rectangles / generated grid | Laycock aggregates elementary regions before roofing; Kada replaces fitted junction cells | C candidate for recognized attachments, D for recovering architectural parts from every minimum cell complex. Need an explicit aggregation/fit mechanism; never retain independent capped gables as a completed graph. |

For D cases we additionally read Sugihara & Kikata (2013), Section 3 of Ren
et al., and Kada's junction and manual-editing discussion. These confirm the
need for roles/compatible parts but do not supply missing arbitrary-minimum-cell
aggregation or interacting junction rules. Stop with an inspectable unsupported
result for those configurations; do not invent them during this task.

## Minimal Graph mapping and planned implementation boundary

1. Keep `Cell`/`Side`/`Adjacency` unchanged. Group atomic shared intervals by
   their incident cell/side pair; a branch end must be complete, all other
   branch sides exterior. Inspect all adjacencies before building a final graph.
2. A **port** is a declared primitive gable-end midpoint/ridge direction; an
   **attachment relation** contains host/branch IDs, incident side IDs, shared
   interval and terminal/middle kind. Contact with zero/one host-side corners
   distinguishes these relations, without any L/T/U footprint classifier.
3. Identify the host by the full branch end versus partial receiving side and
   compatible primitive eave/ridge directions. For a narrow middle attachment,
   branch transverse width must be less than host transverse width. Ambiguous
   roles, unequal slope/height policies, and unsupported arrangements fail.
   There is no new largest-area, centrality or weighted main-structure score.
   Candidate primitives retain their explicit existing orientation policy;
   this series does not silently rotate a square/fat receiver to make a failed
   port match pass. Such configurations may need a declared architectural axis.
   In a terminal relation, `host` names the receiving geometric side, not
   necessarily the higher architectural roof: either primitive can be wider.
   The existing corner refinement preserves the wider ridge accordingly. The
   narrow-to-wide hypothesis specifically governs the new middle rule.
4. Terminal: remove both incident near ports and artificial cut, splice the
   existing corner/reflex junction into the four slope cycles. Equal-width has
   ridge/ridge/hip/valley spokes; unequal-width has the existing two trivalent
   junction refinement, with the narrower ridge terminating lower.
5. Narrow middle: remove branch near port/internal cap. Retain the host ridge
   and opposite slope unchanged. Replace the consumed interval in the host
   slope cycle by `first reflex -> J -> second reflex`; replace the branch
   near ridge endpoint by J in its two faces. J has one ridge and two valley
   edges; no extra hip, internal gable end or artificial-cut edge remains.
6. Equal-width middle: J joins the host ridge. The two portions of the attached
   host slope become separate face cycles; the opposite slope remains one.
   J has three ridge segments and two valleys, matching the T port incidence.
   This is a topology transition, not a coordinate approximation of the narrow
   case. No zero-area host face is emitted at equality.
7. Multiple narrow middle attachments are eligible only when all relations
   identify one host, branches are exterior leaves, axes agree and their
   projected attachment intervals are strictly separated. Build each host face
   cycle from the full ordered set, once. Do not recursively compose pairwise.
   Their inserted paths involve distinct vertices/intervals, so permutation of
   input adjacency cannot change incidence. This conservative applicability
   condition is our adaptation, not a theorem that all CSG merges commute.
8. Add deterministic **initial XY** only after incidence/meanings are fixed.
   It is a noncrossing drawing, not roof-plane intersection or final embedding.
   Pass the unchanged topology to a geometry problem; nonlinear solve is not
   in this series. Independent tests can supply metric witnesses to disprove
   an unrealizable graph without making them the topology generator.

`Face.cells` identifies originating primitive faces, including merged origin
sets where necessary; it is not inferred from a visible solid. Exterior spans
remain owned by the original outline and all internal edges have two incident
faces. Final features are graph-selected before XY/Z solving.

## Other roof types and proof obligations

Keep the four single-rectangle primitives. Flat is naturally one coplanar
outline face rather than one face per cell; this can be a later separate proof.
Multi-cell hip must consume internal caps and use compatible hip/junction
ports: the surveyed hip fitting descriptions do not establish a full arbitrary
compound-hip grammar. Shed requires a consistent declared architectural
direction; local cells must not independently pick it. These are explicit
unimplemented composition cases, not restrictions on the partition contract.

Primary proofs inspect oriented cycles, one boundary, Euler disk, vertex links,
ridge continuation/termination, valley/hip incidence, cell and exterior ownership,
and absence of artificial cuts/internal caps. Use independently authored cycles
and embedding witnesses; inject edge/incidence faults. Metamorphisms include
transforms, cyclic/winding/collinear input changes and adjacency order.
Visuals must distinguish cells/cuts, adjacency, primitive ridge candidates,
retained ridges, valleys, hips and junctions. Unsupported grid 14/20/40 examples
must show their exact unresolved port/aggregation conditions, without a pretend
final graph. Existing production/semantic harnesses remain unchanged.

The first evaluation requires researched terminal and middle operations plus a
sound boundary for multiple attachments. Passing it does not claim a general
roof composer, a nonlinear solve or a final Blender multi-cell mesh.
