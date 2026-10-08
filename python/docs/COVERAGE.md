# Staged coverage

`coverage_inputs_v1.json.gz` freezes six separate corpora (generator
`coverage_corpora.py`, version 1, seed 382901). The grid input is the existing
1000-shape connected-grid stress corpus, not project-wide coverage or a sample
of real houses. Nonuniform orthogonal intervals are independently randomized;
oblique affine variants are stress inputs, not Euclidean equivalence tests.

`audit_coverage.py` measures footprint validity, completed partition search,
architectural interpretation, valid RoofGraph, GeometryProblem, solve and
validated mesh separately. Blender is **unmeasured** in a CPython audit; actual
conversion evidence is provided by the Blender smoke report. Unmeasured is not
an observed failure. The seed is fixed at zero. The audit does not retry a
failed chosen candidate with another seed.

The baseline `canonical/coverage_baseline.json` uses HEAD bcc4213 production
behavior (analytic rectangular solve only). Its failure owners prevent a valid
Graph being reported as a final roof. Detailed all-candidate diagnostic records
are streamed to compressed JSONL, rather than retained in memory.

## Evidence-based blocker classes

A: another retained minimum partition succeeds. B: another assignment of the
same partition succeeds. These are **observed alternative success**, not a
claim that every such rejected graph is repairable. C: a known junction
operation's restricted applicability fails. D: fixed topology cannot currently
be solved. E: several valid choices are retained and selected by seed; this is
not a reject. F: a relation has no justified definition within the declared
input/architectural contract. A relation string alone cannot establish C or F:
`unresolved_B_C_F` explicitly records the missing evidence until research and
local geometry distinguish interpretation from operation insufficiency.
Downstream junction and solve failures are censored when an earlier relation
rejects an assignment. Conditional sole blockers are not promised coverage gains.
