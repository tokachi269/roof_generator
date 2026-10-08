# Minimum partitions and architectural part interpretation

Starting SHA: `7d33cb84dc6c3ed32af2cf154770db3df6981128`.
This note is committed before production changes. This series ends at part
interpretation; it does not add roof junctions, nonlinear solving or Blender meshes.

## Reread sources and actual processing order

| Source | Elementary decomposition | Alternative partitions | Aggregation | Main/branch interpretation | Roof unit | Junction timing | Current mapping |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [Laycock & Day 2003](https://www.sthu.org/misc/SKRW14/papers/LaycockDay_2003_AutomaticallyGeneratingRoofModelsBuildingFootprints.pdf), Section 7, Fig. 4–6 | Rays from every reflex vertex produce elementary rectangles. | Skeleton-grown axis-aligned regions determine the grouping, not a minimum-candidate ranking. | Collect contained elementary rectangles per grown region, resolve shared membership by set difference, then obtain the exterior boundary. | Skeleton lines identify larger roof structures; no largest-area main rule. | An aggregated exterior boundary, not every elementary rectangle. | Assign roof models only after grouping, then merge one/two-collinear-edge cases. | Adopt boundary cancellation and explicit cell membership; do not invent a replacement for skeleton-grown regions. Hu supplies a different published combination interpretation below. |
| [Hu, Fan & Noskov 2017](https://doi.org/10.1080/17538947.2017.1373867), Sections 3.1–3.5, Fig. 3–19 | Advanced minimum non-overlapping cover uses good chords, matching, MIS and free-reflex completion. | Section 3.1 enumerates all MISs and both horizontal/vertical completions. The example has 5 MISs × 32 directions = 160 partitions. | Section 3.2 merges adjacent collinear equal-width centerline segments. Sections 3.4/3.6 use compound L-units containing several rectangles. | Full short end versus long side gives side attachment; two partitions can assign the common corner section to either member. Symmetry preserves equal options; it does not force one main axis. | Rectangle or compound L-unit with constrained member ends; not independent capped roofs. | Combination and symmetry constraints follow partition selection, before recommending roof primitives. | Separate candidate enumeration, exact minimum certificate, part/combination graph and recommendation. Retain alternative receiver assignments and square axes rather than silently choose an area maximum. |
| [Kada & McKinley 2009](https://www.isprs.org/proceedings/xxxviii/3-w4/pub/CMRT09_47.pdf), Sections 2.1–2.4, Fig. 8–11 | Generalized cells, not a fixed minimum partition. | Manual decomposition-line changes and fitted data, not footprint-only minimum enumeration. | Cells can become connecting blocks after neighboring primitive fits. | Basic/connecting/manual shape classes; neighboring fitted types, parameters and arrangement determine compatibility. | A fitted basic cell or replacement junction block. | Fit primitives first; reexamine consecutive-side or at-least-three-side neighbor cells; select the compatible connector joining most neighbors. | Reserve junction replacement for downstream topology. Part interpretation cannot invent missing LiDAR fits or use the solver to choose roles. |
| [Sugihara & Hayashi 2007](https://www.jstage.jst.go.jp/article/journalac2003/16/0/16_0_309/_pdf), Section 4(2), pp. 312–313 | Repeated short-DL rectangle extraction; recompute RL data until a rectangular body remains. | Different extraction decisions; no all-minimum solution guarantee. | Extracted branch plus remaining body form the architectural arrangement. | DL supplies branch width; shared slopes make a wider main higher. Branches are identified before roof extension. | Detached/extracted rectangle and remaining main body. | Narrow roof is extended into wider main after placement. | Use the local end/side and transverse-width relation; do not restore its greedy partition or make the global largest rectangle main. |
| [Sugihara & Hayashi 2006](https://www.jstage.jst.go.jp/article/journalac2003/15/0/15_0_67/_pdf), Sections 3–4 | Fat rectangles extracted until the body has four vertices. | No advanced minimum-candidate enumeration. | CG/CSG construction and placement. | Extraction order identifies body and detached rectangles. | Rectangular building parts. | Construction follows partition. | Do not attribute the later narrow/wide extension to this paper. |
| [Sugihara & Kikata 2013](https://researchmap.jp/sugihara1128/published_papers/14649928/attachment_file.pdf), pp. 479–480, Fig. 3 | Narrow-branch extraction improves earlier fat-rectangle partition. | Does not supply minimum-space candidate pruning. | Detached rectangle extended toward wider/higher main. | Same local width and remaining-body interpretation. | Connected architectural parts, not arbitrary elementary roofs. | Extension follows part determination. | Supports the local width contract, not new global role scores. |

The Hu author-uploaded full PDF was downloaded and read, including combination
figures, AllMaxInd pseudocode and Section 5. Publisher access returned HTTP 403;
the full author copy is at
[ResearchGate](https://www.researchgate.net/publication/319650645_Roof_model_recommendation_for_complex_buildings_based_on_combination_rules_and_symmetry_features_in_footprints).
Other full papers were reread from local originals. PDFs/figures are not redistributed.

## Why the fixed current cells fail

| Existing case | Current minimum cells | Missing interpretation |
| --- | ---: | --- |
| U | 3 | Canonical vertical completion gives two full-length vertical members and a short transverse connector. Alternative horizontal completion gives a transverse receiver with two terminal branches. Width/port logic must inspect candidates, not permanently accept the first axes. |
| Cross | 3 | Four good diagonals have matching size 2. Horizontal and vertical maximum independent sets give equally minimal main-axis alternatives. Symmetric input cannot select one semantic direction from matching order. |
| Residential | 4 | Canonical receiver has one middle and two terminal candidates. Current composer only accepts isolated terminal or all-middle leaf arrangements. Compound corner units plus inter-unit side attachments must precede junction decisions. |
| Grid 14 | 5 | Diagonal choice and three unresolved reflex completions create different end/side versus parallel-side relations. One canonical split is not a roof recommendation. |
| Grid 20 | 7 | Several regions and four completion choices; square members and compound corners can leave axis/receiver ambiguities. Need grouped boundaries and relations, not independent gables. |
| Grid 40 | 12 | Six matching edges and unresolved completions make candidate choices meaningful. Several square/parallel/interacting relations need explicit interpretation options; no assumed single host. |

A useful restriction follows from the minimum contract: two disjoint minimum
cells cannot have an exactly rectangular union, or replacing them by that union
would yield fewer rectangles. Thus simple bounding-box aggregation cannot be
the general solution. Compound architectural units can have orthogonal concave
boundaries while retaining their member rectangle geometry and combination
constraints. Such a unit is not yet one parametric roof primitive.

## Candidate contract and boundedness

Keep the existing `partition`/`decompose` result and its certificate unchanged.
Add an opt-in candidate API using the same chords, conflict graph, matching and
subdivision validators. Enumerate maximum independent sets by choosing one
endpoint of each matching edge, forcing every unmatched graph vertex into the
set. This is equivalent to Hu's endpoint branching: a maximum independent set
of size |V|−|M| must contain every unmatched vertex and exactly one endpoint of
each matched edge. Propagate conflicts before branching; this is exact pruning,
not a roof heuristic. Enumerate both completion axes in canonical reflex order.
Every returned subdivision must attain `r − |MIS| + 1` cells.

The paper supplies **no polynomial candidate-count guarantee or safe top-k
pruning**. Explicit work/candidate budgets therefore report an incomplete search
and prevent a best-partition recommendation; they never call a truncated pool
optimal. Caller-adjustable bounds are resource contracts, not scoring rules.
Deduplicate identical rectangle subdivisions. Preserve the original partition
and close candidates under actual footprint symmetries by transforming certified
cuts; symmetry images remain minimum. The completion order is explicit: the
family includes both axis choices in the existing canonical order, not an
unproved claim to enumerate every possible Steiner/cut-order realization.

## Architectural contract and published rules

Use a small `ArchitecturalPartGraph`, separate from RoofGraph, with member Cells,
exact exterior cycles/spans, consumed cuts, member axis domains, local
combination relations and symmetry information. No ridge/valley/XYZ/roof type
is created. Connected compound corner combinations form L-units in Hu's sense;
one-line combinations represent continuation. Recognizing a local end/side
relation is not an L/T/U **footprint** classifier.

- Adjacent equal-width collinear members can be one continuation unit (Hu 3.2);
  record actual canceled atomic cuts and do not add bounding-box area.
- A complete short end on part of a perpendicular long side identifies side
  attachment. At a receiving-side corner, retain the compound corner relation
  and possible receiver assignments across candidates (Hu 3.4.3). Strictly
  internal attachments remain inter-unit relations (Hu 3.4.2).
- Only the local transverse-width contract establishes a narrow branch/wider
  receiver. Equal width and square-axis choices remain explicit options.
- All relations are collected before grouping. Group connected unambiguous
  corner/continuation relations simultaneously, not by pairwise roof merging.
  Exact exterior cycles come from cancellation of oriented member boundaries,
  the structural part of Laycock's exterior-boundary step; no Boolean is used.
- Unclassified parallel/partial-end contacts are retained as unresolved analytic
  adjacency. Keeping a part graph is not a claim of a realizable roof topology.

Hu 3.3 recommends `−1 per fragment −2 per parallel pair +1 per symmetric
subcluster pair`. Keep these published terms visible, not invent weights.
The original fragment threshold is 3 metres (Section 5.2); expose unit conversion
and threshold explicitly. **Keep** fragments in membership/provenance, unlike
the paper's later omission. A rectangle centerline here is an analytic axis,
not a roof ridge. Hu's connected reflection-pair criterion will be implemented
with exact, maximal matched components (including split members at an axis),
not a heuristic reward for every equal-sized pair. Exact comparisons use existing
normalized tolerance, not the paper's 0.3/0.5 metre outline generalization.
Retain all top-score candidates and symmetric direction alternatives; a chosen
inspection index is deterministic serialization, not semantic uniqueness.

These are explicit adaptations: exact minimum input in place of elementary
skeleton/fitted regions; compound grouping from published combinations; retaining
fragments; maximal reflection components; bounded incomplete-search reporting.
The original papers do not supply one complete arbitrary-footprint roof grammar.
Do not invent it in this series. Hu's end-triangle options and probability model
belong to future roof topology recommendation, not this roof-type-free contract.

## Proof and stop boundary

Independent proofs must check certified minimum count, coverage/disjoint cells,
complete cell membership, canceled cuts, exterior spans, exact grouped exterior,
local relation consistency, adjacency permutation and geometric metamorphisms.
Cross must retain symmetry-related main-axis alternatives. Inspect original U,
Cross, Residential and grid 14/20/40 with candidates, grouped units, relations
and unresolved reasons. Generated tests must not be the only oracle.

No existing roof composer/optimizer/addon is rewired during this series.
After inspection/measurements, evaluate whether the part graph provides enough
architectural information for subsequent generic topology composition. Ambiguous
or unsupported contacts remain blockers; no silent independent-roof fallback.
