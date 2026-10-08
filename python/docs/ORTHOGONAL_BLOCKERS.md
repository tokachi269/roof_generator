# Orthogonal relation evidence and supported operation boundary

## Published rules versus diagnostic words

Hu/Fan/Noskov 2017 §§3.3–3.5 was reread in full: parallel long sides receive a
recommendation penalty, not a junction template. §3.4.1 eliminates one-line end
triangles; it does not prescribe an offset/width-step ridge junction. §3.4.3 and
Fig.18 combine constraints on all neighboring ends, rather than selecting each
end independently. Laycock/Day 2003 §7 Fig.6 merges models with compatible
collinear exterior edges. Sugihara/Hayashi 2007 pp.312–313 Figs.4–6 extends a
narrow branch into a wider receiver, including several branches. Kada/McKinley
2009 §2.4 Fig.11 replaces compatible fitted junction blocks using neighboring
roof data; a footprint alone does not provide those fitted choices. None of
these sources supplies arbitrary partial-end, offset-ridge or parallel-contact
incidence for the present footprint-only contract.

The all-minimum-candidate diagnostic (`canonical/partition_selection_probe.json`)
checks the **same** 1000 frozen orthogonal stress inputs before adding an operation.
No extra valid topology is found among the previously unretained partitions.
Thus A is not an observed rescue for these unsupported cases within the searched
family. This is not a proof about arbitrary completion orders or all architecture.

| Blocker | Current owner and evidence | Decision |
| --- | --- | --- |
| parallel | Architecture has long-side contacts without a justified receiving/branch port; Hu ranking penalizes them. No successful alternative in this corpus | B/C/F unresolved research boundary, not automatically C; no invented parallel junction |
| continuation | Architectural compound preserves members; actual contacts have width step and/or transverse offset. Same-width aligned cells could be merged and contradict minimum count | Missing contract for step/offset junction (C) and insufficient architectural specification (F within current input contract); no plain continuation rewrite |
| partial_end | Neither full branch cap nor proved receiver-side port is available. Hu cap choices do not specify incomplete cap incidence | Architectural interpretation B and missing justified template F; no graft of a partial cap |
| mixed terminal/middle | Full leaf caps, one receiver and separated ports already identified, but current dispatcher refuses their simultaneous combination | C: compose the existing published restricted operations together |

These labels are evidence scope, not a claim that a building can never have a
roof. The detailed audit retains unresolved categories where it cannot prove
which additional architectural information is sufficient. Valid ambiguity E
remains seedable; a missing incidence rule never enters seed selection.

## Simultaneous terminal plus middle adaptation

This is an indexed-graph adaptation of existing terminal and middle incidence,
not a newly attributed published all-purpose junction algorithm.

Applicability: one receiver; all other members exterior leaves; every shared
boundary consumes a full branch cap; distinct receiver-end terminal ports; middle
branches strictly narrower than the receiver. Middle intervals must be disjoint
and outside the terminal replacement's conservative longitudinal enclosure
`max(receiver_width, terminal_branch_width)` from the consumed end, on either
receiver eave. This is a sufficient **noninteraction condition**, not a roof
quality score or minimum-partition selection heuristic. Terminal ridge/hip/valley
vertices lie inside that enclosure under the established equal-pitch witnesses;
the middle valley splice lies inside its branch interval. Consequently their
cycle neighborhoods do not overlap.

Recognize the full port set before editing. Replace terminal corners as before;
splice each middle valley path into its receiver eave, retaining the receiver
ridge. Allocate the branch ridge and two valley spokes for each middle port.
Rewrite receiver face cycles once with all ordered insertions. Distinct edits
preserve oriented incidence and Euler disk; validate the resulting graph and its
explicit pitch embedding. No sequential merge, envelope, Boolean or shape name
is used. Equal-width mixed ports and overlapping enclosures remain unsupported.

Independent proofs use new parameterized branch networks, literal equal-pitch
vertices/incidence, a near-end counterexample, relation-order and rigid-transform
metamorphisms. This extends a proved relation operation; it does not assert that
parallel/partial-end/offset-continuation has thereby been implemented.
