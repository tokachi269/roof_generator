# Roof-region selection and ownership

This research follows diagnostic commit `84934f1`, now pushed to `origin/main`.
The missing decision is roof-oriented region decomposition, before relations,
ends and RoofGraph. Minimum partition remains analysis and provenance. Whole
minimum Cell sets cannot express all demonstrated aggregation configurations.
That representational limitation is established independently of whether any
particular configuration becomes a valid roof. An atom layer is one possible
representation; it is not the architectural decision itself.

## Published rules and their domains

**Laycock & Day 2003**, section 7, Figure 4, PDF page 3:
the collection/difference sequence supplies no general priority. The printed
post-difference inventory omits rectangle 3. Under the diagnostic's first-claim
interpretation, preserving red's other cells implies red before green, and
preserving blue's cells implies blue before green and pink. These constraints
still do not determine red versus blue ownership of 3; no order reproduces the
printed complete result while covering the footprint. A drawing-consistent
interpretation cannot establish an area-first general rule.
[Publisher paper](https://dspace.zcu.cz/bitstream/11025/991/1/G67.pdf),
[diagnostic receipt](authority/laycock/figure4-check.json).

**Hu et al. 2017**, sections 3.3–3.6 and 5.2:
partition scores penalize fragments (-1) and parallel contacts (-2), and reward
symmetry (+1). Fragments use an empirical 3 m threshold and are ignored later.
L-junctions admit shared or T options, with common-section ownership on either
best partition. Multiple combinations on an end impose simultaneous constraints;
L-units group adjacent junction/end events for roof-shape probabilities. This is
not arbitrary polygonal AAR ownership. Its local alternatives support retaining
multiple possibilities, but its scoring does not resolve the diagnostic's
overlapping collections. These are recommendation priors, not mesh or region
validity proofs. Do not import fragment omission into full-footprint coverage.
[Author-uploaded full text](https://www.researchgate.net/publication/319650645_Roof_model_recommendation_for_complex_buildings_based_on_combination_rules_and_symmetry_features_in_footprints).
The publisher reader returned HTTP 403; sections were read from the author's
full-text upload. The term defined there is L-unit, not a generic compound-region
ownership solver.

**Sugihara & Hayashi 2007**, section 4(2), printed pages 312–313,
Figures 4–6: cut off one rectangle, prefer the shorter of a reflex vertex's
two dividing lines, require branch width below receiving-main width, and
recalculate after removal. This selects cuts for a branch/body partition;
it does not allocate overlapping Laycock collections. Equal-width, simultaneous
cut ties and general offset ownership are not resolved by these conditions.
[J-STAGE full paper](https://www.jstage.jst.go.jp/article/journalac2003/16/0/16_0_309/_pdf).
The full six-page PDF was extracted and printed page 313 visually inspected.

**Sugihara & Hayashi 2008**, printed page 369, criticizes the number of
elementary rectangles and cumbersome collection/merge on complex polygons.
This passage was verified in the search-indexed primary-paper excerpt.
[Paper excerpt](https://citeseerx.ist.psu.edu/document?doi=63dfa4c8c74ac58d6a172a66737c168f50971472&repid=rep1&type=pdf),
[publisher metadata](https://www.sciopen.com/article/10.1016/S1007-0214%2808%2970176-7).
The attempted PDF download returned HTML, so no additional 2008 algorithm or
tie rule is claimed as read. The 2013 author-hosted PDF was also inaccessible
in this investigation; it supplies no newly verified rule here.

Within these inspected sources, no complete general ownership priority was
established. This is a bounded research result, not proof that no such algorithm
exists in the literature. Area-first and whole-Cell-preserving orders remain
diagnostic conventions. Neither becomes production policy.

## What seed selection must receive

The existing seed choice selects validated topology candidates. It cannot
turn a provisional collection order into an architectural decision. The
following contract is a project adaptation consistent with the user's direction,
not a verbatim algorithm extracted from the papers:

1. A candidate supplies actual region polygons covering the original footprint,
   with disjoint interiors and positive area. Every leftover area is accounted
   for, including attachments. The original minimum Cells supply intersection
   provenance, not region boundaries or roof directions.
2. Each architectural region has one connected support. A disconnected union
   may be represented as explicitly separate regions only when their roles and
   relations are defined; silently splitting it is another architectural choice.
   Holes and nonrectangular supports require explicit roof-model contracts.
3. Region models supply admissible member/ridge directions, end constraints
   and supported relation choices. All shared-end and symmetry constraints are
   resolved globally. A relation label or successful mesh is not sufficient.
4. Generate and validate final incidence only through supported rules. Keep
   architectural preference and construction rejection observable separately.
   Undefined region models, merge grammar, uncovered areas or incomplete
   candidate search remain unsupported rather than receiving a guessed repair.
5. Deduplicate by canonical region geometry **and resolved architecture/topology**,
   preserving source histories as provenance. Geometry alone is insufficient
   when two legitimate architectures use the same regions. Seed chooses only
   among admissible complete candidates; equivalent source orders must not
   multiply a candidate's chance. Any ranking prior must declare its domain.

The proposed pipeline is therefore candidate region decompositions → explicit
architectures/ends → validated topology candidates → seed. It is not permutations
of arbitrary first-claim orders → seed. The growth probe also remains incomplete
for Grid20/40, so this contract is not yet an implemented candidate generator.

## Additional diagnostic checks

`audit_region_ownership.py` reads the saved report without computing another
skeleton. It removes collection labels from 2D region-set identity and checks
exact atom coverage, polygon validity, footprint union and area. These checks
do not evaluate roof validity or naturalness.

| Input | Labelled configurations | Distinct region sets | Configurations with a disconnected collection |
| --- | ---: | ---: | ---: |
| Screenshot 1 | 48 | 48 | 19 |
| Screenshot 2 | 8 | 8 | 1 |
| Screenshot 3 | 10 | 10 | 1 |
| Screenshot 4 | 4 | 4 | 0 |
| Grid14 | 56 | 51 | 0 |

All fully enumerated alternatives cover their footprints in 2D. This says
nothing about their roof incidence. In particular, screenshot 4's larger
central rectangle is not a completed natural-roof proof. Its attached residual
regions still need explicit models and merge decisions.
[Full 13-input check](authority/laycock/ownership-geometry.json).

## Representation decision

`Part.region` should be the actual support geometry, with area-intersection
provenance into source partitions. The permanent representation (orthogonal
polygon versus common atom set) remains undecided. If atoms are used, they are
a Boolean/coverage computation representation; their boundaries have no default
ridge, valley, member or junction meaning. A polygon representation likewise
does not determine roof topology by itself.

Before schema implementation, define the admitted region/model candidate family
and supported merge incidence on the four screenshot inputs. Demonstrate a
roof-valid larger-region candidate and its constraints, not just a covering
union, and verify that search order/Cell boundaries do not select it. The
current research resolves that a general published ownership rule has not been
recovered from the inspected sources; it does not resolve this candidate grammar.

Production, skeleton implementation and installed ZIP are unchanged by this
research. No new usable roof scenario is claimed. Reproduction:

```bash
python python/audit_region_ownership.py --report python/docs/authority/laycock/report.json.gz --output python/out/authority/ownership-geometry.json
```
