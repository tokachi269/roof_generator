# Remaining region model domain

This diagnostic changes no production roof generator and adds no usable roof
scenario. It investigates why the remaining two screenshot approximations
still fail after polygon-authoritative supports and the opposite-eave repair.

## Question and finite search

The maximal/all-receiver probes considered one receiving rectangle and exterior
rectangular leaves. Their failures alone could have come from that star-shaped
architecture restriction. `probe_region_covers.py` therefore enumerates every
nonoverlapping rectangular cover in the coordinate arrangement induced by the
footprint vertices, not only minimum partitions or single-receiver candidates.

Temporary coordinate boxes are search bookkeeping. Every complete cover enters
the same public `propose_regions` acceptance path as actual polygon regions.
The original minimum Cells never choose supports or roof axes. No disconnected
owner is silently repaired, no leftover area is omitted, and no area/valley
score ranks a cover.

All contained rectangles with boundary-coordinate endpoints are enumerated.
Depth-first exact cover always covers the first unowned coordinate box, avoiding
permutation duplicates. At most one member per occupied box is possible; the
10-member limit therefore covers every member count for these four inputs.
The explicit work limit is 100,000; all four searches finish below it.
Coordinates and polygon acceptance use the existing normalized numerical
allowance; this is not a claim of symbolic exact arithmetic.

Existing geometric relation domains filter axes that would require unsupported
parallel/partial-end rules. Remaining assignments are checked with the actual
global end and exact whole-member symmetry constraints. Full coincident-end
continuation obligations remain distinct from unsupported offset continuation.
Composition is attempted only after those constraints pass. No solver is used
to select topology or to fill a missing junction.

## Observed results

| Screenshot | Coordinate boxes | Contained rectangles | Complete covers | Covers with no supported axes | Remaining axis assignments | Compatible end choices | Constructed graphs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 10 | 26 | 149 | 143 | 9 | 0 | 0 |
| 2 | 6 | 12 | 13 | 9 | 7 | 12 | 1 |
| 3 | 7 | 17 | 34 | 31 | 4 | 0 | 0 |
| 4 | 4 | 7 | 5 | 3 | 3 | 4 | 1 |

The nine remaining axis assignments on image 1 and the four on image 3 all
reject before publishing end choices because of offset continuation. Other
covers have no axis assignment within the current supported relation domain.
This is not evidence that offset continuation should automatically become a
junction. Its actual model/merge rule is still undefined.

The one graph each on images 2 and 4 equals the previously recorded graph from
the explicit region API. Other end configurations reject the existing isolated
L-extension applicability. This probe does not newly solve or render any roof;
it checks model-domain and composition evidence only. A work limit of 1 also
correctly returns incomplete, with zero constructed graphs.

## What this establishes

Within this finite coordinate-rectangle family, failures of images 1 and 3
cannot be repaired merely by adding more covers, allowing nonminimum rectangle
partitions or removing the single-receiver restriction. A broader region roof
model or a defined offset/partial-end merge grammar is missing. Changing the
Cell/Atom representation cannot supply that model.

This does **not** enumerate arbitrary free-coordinate regions, nonrectangular
support models or all architectural interpretations. It does not prove the
footprints cannot have natural roofs. It also does not authorize inventing a
graph rule for an unknown contact merely to pass the four-case gate.

## Laycock model boundary reread

Laycock & Day sections 6 and 7 were reread, including the local full PDF's
fourth page and Figure 6. Section 7 supplies aggregation before roof assignment.
Section 6's general polygon roof models use straight skeleton construction and
modifications. The project's permitted skeleton use remains **aggregation guide
only**; those model-generation steps have not been implemented as a RoofGraph
backend. Thus the aggregation guide does not itself provide our missing
nonrectangular fixed-topology model contract.

Figure 6 illustrates one- and two-collinear-edge merge cases, including
nonrectangular/overlapping model arrangements. It does not provide a complete
indexed incidence and parameter rule for every arbitrary offset/end arrangement.
The bounded drawings remain useful references, not an executable general
grammar. This reread adds no runtime skeleton dependency or roof edge source.
[Primary full paper](https://dspace.zcu.cz/bitstream/11025/991/1/G67.pdf).

The current four-case production gate is still unmet. Images 2 and 4 embed from
explicit proposals; default proposal discovery remains minimum-based. Images
1 and 3 require further model work with stated applicability, incidence and
independent embedding evidence. The existing default-generator improvement on
frozen grid `generated_0356` and its coverage audit remain valid, separate work.

```sh
python python/probe_region_covers.py --inputs python/tests/fixtures/user_roof_images_v1.json --max-members 10 --max-work 100000 --output python/out/authority/covers-all-images.json
python python/probe_region_covers.py --inputs python/tests/fixtures/user_roof_images_v1.json --case user_image_3_band_and_lower_corner --max-members 10 --max-work 1 --output python/out/authority/covers-incomplete.json
```
