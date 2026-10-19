# Historical snapshot

Scope: full-Line empirical proof notes extracted from implementation at `62809e7`. This is not current authority.

# Implementation proof notes

Development-only NumPy SVD and Shapely containment/intersection predicates
independently test planarity, footprint coverage and interior overlap. Containment
of each patch, pairwise disjoint interiors and equal total area imply coverage;
this avoids depending on one floating union overlay. A frozen step-wall case
demonstrates a raw GEOS union losing area despite those three checks and a
bounded-precision overlay agreeing. Raw union error stays in the diagnostic
record. No production coordinates are snapped for this test.
Those packages are not imported by the
kernel or its Blender script. The numerical oracle is evidence independent of
the contact rewrite; it is not a runtime fallback.

The fixed tests include an actual component split, two distinct contacts at the
same time, a six-source event, all 63 nonempty EAVE subsets on a concave L,
nonparallel full gables, exact rational rigid transforms, winding/cyclic changes,
collinear subdivision, limits, cache independence and numeric range failures.
All 63 L assignments yield 59 validated complexes, two negative-plane witnesses
and two scoped stationary-front certificates, with no kernel failure. Two distinct exact event times may round
to the same double and are still processed separately.

The frozen multi-corpus and mixed-role results, timings, SVGs and Blender evidence
are reported in [LINE_KERNEL_EVALUATION.md](LINE_KERNEL_EVALUATION.md). A successful
finite corpus does **not** prove universal completeness for every degenerate
simple polygon. The source/contact rules and postconditions are explicit, but
formal exhaustiveness/termination of the zero-speed contact model and a
sufficient independent admissibility criterion remain obligations before an
unconditional universal guarantee is advertised.

## Remaining gates

- Establish those universal zero-speed/completion obligations and automatic
  admitted intent generation, including an inclined-only architectural profile. A necessary plane check alone
  is not that policy.
- Transfer kernel authority into the addon and verify packaging/input transforms;
  the current standalone Blender script is not that integration.
- Define collinear partial transitions before accepting them.
- Implement actual Arc evolution/splice conventions, then general curves. Sampling
  straight chords is not a curve-source kernel.
- Continue performance work on the measured exact-predicate/noding costs.
  Existing nonlinear solve timings are not this kernel's construction budget.
