# Laycock aggregation applicability

The [author-uploaded paper](https://www.researchgate.net/profile/A-Day-2/publication/2472808_Automatically_Generating_Roof_Models_from_Building_Footprints/links/00463530c6ebb93f72000000/Automatically-Generating-Roof-Models-from-Building-Footprints.pdf)
was read as full text and visually reviewed on PDF pages 3–4 (Figures 4–6).
The publisher endpoint timed out and the author endpoint denied a direct
download; a previously referenced public mirror supplied the same titled paper
for local rendering. During the subsequent authorized diagnostic, the
[publisher PDF](https://dspace.zcu.cz/bitstream/11025/991/1/G67.pdf) also became
accessible and was checked. The paper and its figures are not redistributed here.

Section 7 builds an elementary rectangle grid, derives axis-aligned guides
from a straight skeleton, grows collecting regions, resolves their elementary
rectangle ownership, then assigns roof models and merges them. Figure 6
illustrates two merge cases on those already interpreted regions. It is not
a rule to turn every minimum-partition parallel contact into a junction.

## Current code boundary

`ArchitecturalMember` currently references a complete minimum Cell and takes
its geometric direction domain from that Cell. `ArchitecturalPart` publishes
membership and its canceled boundary. `RoofEnds` can choose shared/T incidence
for supported member contacts. None of these records supplies the paper's
skeleton-derived collecting guide or a roof model for an arbitrary collected
nonrectangular region.

Consequently, interpreting `parallel` as a direction to merge two existing
gables would skip the region-interpretation decision again. Suppressing their
valley afterward would also leave the unproved slope and ridge arrangement.
The implementation must not fill those missing decisions from the old output,
from valley counts, or from operation availability.

For the user's staggered bands, the current end-state implementation remains
partial: short-end constraints do not determine long-side region aggregation.
The required missing contracts are the selected guide/region ownership and
the region's fixed roof incidence. A straight-skeleton production substitution
was expressly excluded by the task and was not introduced. The paper supports
aggregation as a necessary stage; this review does not establish a permitted
general offset RoofGraph implementation for the current backend.

The read receipt is in
[the research record](authority/user-images/laycock-review.json). Current
[factory-roof evidence](USER_FACTORY_ROOF_EVIDENCE.md) remains a historical
reproduction, not a completed natural-roof repair.

## Authorized diagnostic follow-up

After `587cf10` was pushed, the user authorized section 7 Steps 1–5 solely as an
ArchitecturalPart aggregation guide. Skeleton edges must not become final roof
features or a RoofGraph backend. Before production changes, compare regions
against minimum Cell unions on all four screenshot approximations and the
specified structured/grid inputs. Data-model changes remain conditional on
that representability investigation.

The [diagnostic result](LAYCOCK_REGION_DIAGNOSTIC.md) records 13 inputs, Figure 4
raw collection reproduction and priority-sensitive partial-Cell witnesses.
It distinguishes the paper's stated sequence from an explicit centred-growth
probe and ordered ownership conventions. These do not yet establish the
production gate or repair the four screenshot roofs.
