# Evidence storage

The [documentation index](../README.md) owns current status and specifications.
This directory holds fixed inputs and frozen observations, not instructions for
the current generator. No baseline artifact was deleted in this reorganization.

| Area | Retention contract |
| --- | --- |
| `inputs/corpora/` | Four frozen, versioned corpus files moved byte-for-byte from `canonical/`; consumed by tests and corpus/audit tools. Never regenerate them in place to make a changed algorithm pass. |
| `inputs/partition/` | Ten input-only records extracted from the old partition inspection snapshots. The inspector and selection tests consume these without depending on measured outputs. |
| `results/` | All retained phase observations, source receipts, images, inspections, timing/profile samples and manifests, including the original partition inspection records. |
| [catalog.json](catalog.json) | Original path to current path, byte length, SHA-256, current literal source consumers, extracted-input provenance and exact duplicate groups. |

Other fixed inputs already under `python/tests/fixtures/` remain there. The catalog
lists direct literal path consumers; tools that construct paths from names (for
example the partition inspector) are also documented here. It is not a complete
runtime dependency graph.

## Frozen provenance and old paths

Results and their manifests retain their **original Git-blob bytes** at `62809e7`,
independent of Windows checkout-only CRLF conversion. Embedded source
paths, report locations, commit IDs and historical hashes describe the recorded
execution; rewriting them would falsify that receipt. Resolve a historic path
through `catalog.json` to locate its current artifact. Current Markdown links,
commands, scripts and tests use the new paths. Historical source hashes do not
claim to fingerprint today's moved/edited documentation.

`results/kernel/` contains the original convex proof; the live kernel contract is
under `../kernel/`. `results/line-kernel/` contains full-Line observations. The
two proof scopes must not be conflated with packaged-addon support.

## Regeneration and retention review

Run reproduction commands from the linked reports into ignored `python/out/`,
then compare observations with the frozen evidence. Do not overwrite historical
results as part of a normal test run.

| Outputs | Documented producer / reproduction entry |
| --- | --- |
| Current release mesh/UV/material observations | `python/blender_smoke_test.py`; [angle evaluation](../history/ARBITRARY_ANGLE_EVALUATION.md) |
| Corpus outcomes | `python/audit_coverage.py`; [coverage methodology](../history/COVERAGE.md) |
| Full-Line SVG/JSON/OBJ, timing, Blender meshes | `probe_line_kernel.py`, `benchmark_line_kernel.py`, `blender_line_kernel.py`; [evaluation](../history/LINE_KERNEL_EVALUATION.md) |
| Original convex proof SVG/meshes | `probe_roof_kernel.py`, `blender_kernel_proof.py`; [initial proof](../history/KERNEL_CONVEX_PROOF.md) |
| Partition/interpretation diagrams | `inspect_architectural_parts.py`; [interpretation evaluation](../history/ROOF_PART_INTERPRETATION_EVALUATION.md) |
| Historical comparison/aggregation probes | Commands and dependency/revision scopes in the corresponding [research records](../README.md#complete-inventory) |

Some historical screenshots, source-read receipts and one-off experiment outputs
do not have a complete current regeneration recipe. They remain evidence, not
disposable build output. Reproducibility has not been re-proved by rerunning all
historical algorithms in this documentation change.

Exact duplicate groups are listed in `catalog.json` as **retained review
candidates**. Equal bytes alone do not prove equal provenance or that a referencing
report can lose its own artifact. No duplicates, screenshots or results are
removed without a separate reviewed deletion list. No paper figures are added.

Check local links, hashes and extracted-input equivalence with:

```bash
python python/check_docs.py
```
