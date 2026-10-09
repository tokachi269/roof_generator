# Tools and verification

The resolved end-state model, proof boundaries and remaining unsupported
combinations are described in [roof-end authority](docs/ROOF_END_CONSTRAINTS.md).

All tools use the distributable `roof_generator.core` under `addon/`.
Runtime needs Python's standard library. `requirements.txt` declares development
oracles only; Blender installs the ZIP without pip or external wheels.

The optional `laycock_regions.py` diagnostic uses only footprint/partition APIs
and external skeleton/polygon oracles; it creates no RoofGraph. It probes section
7 steps 1-5 before any production region-model change. Install its dependencies
into an isolated directory, then inspect the declared growth/priority variants:

```bash
python -m pip install --target python/out/laycock-deps -r python/requirements-laycock.txt
python python/laycock_regions.py --inputs python/tests/fixtures/laycock_inputs_v1.json --output-dir python/out/laycock
python -m unittest discover -s python/tests -p test_laycock_regions.py
```

The current run used the existing development Shapely/Matplotlib and installed
only `py_straight_skeleton==0.1.0` with `--no-deps` into that directory.

```bash
python -m pip install -r python/requirements.txt
python -m unittest discover -s python/tests
python python/build_addon.py
python python/build_addon.py --check --output packages/roof_generator-1.3.0.zip
python python/inspect_rectangular_partition.py --help
python python/inspect_architectural_parts.py --help
python python/inspect_roof.py --fixture cross --seed 7 --output python/out/cross.json
python python/benchmark_generation.py --output python/out/performance.json
python python/benchmark_generation.py --samples 3 --warmup 1 --buildings 24 --output python/out/authority/performance.json
python python/benchmark_roof_mesh.py --samples 3 --buildings 24 --output python/out/authority/mesh-performance.json
python python/inspect_authority.py --inputs python/tests/fixtures/authority_inputs_v1.json --output python/out/authority/inspection.json
python python/authority_diagrams.py --before python/out/authority/inspection-before.json --after python/out/authority/inspection-after.json --output-dir python/out/authority/diagrams
python python/roof_gallery.py --before python/out/authority/blender-end-state-before --after python/out/authority/blender-end-state-final --output-dir python/docs/authority/end-state/gallery
blender -b --factory-startup --python-exit-code 1 --python python/blender_authority_acceptance.py -- --zip packages/roof_generator-1.3.0.zip --inputs python/tests/fixtures/authority_inputs_v1.json --output-dir python/out/authority/blender
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test.py -- --zip packages/roof_generator-1.3.0.zip --output-dir python/out/addon
```

`inspect_roof.py` reports all validated alternatives, rejected assignments,
selected candidate, its resolved end states, and GeometryProblem. Each gable
candidate records the shared/extension choices before composition; flat roofs
have no pitched-roof end configuration. Its SVGs distinguish artificial cell
cuts and actual graph features. `inspect_junctions.py` is a developer-only
inspection of individual port operations, not a second generation API.

Coordinate API:

```python
import sys
sys.path.insert(0, 'addon')
from roof_generator.core.generation import GenerationSettings, prepare_generation, generate_roof

settings = GenerationSettings('gable', seed=42, reference_direction=(1, 0))
roof = generate_roof(((0, 0), (12, 0), (12, 6), (0, 6)), settings)
problem = prepare_generation(((0, 0), (12, 0), (12, 6), (0, 6)), settings).geometry_problem
```

Mesh coordinates are in the normalized intrinsic frame. Use the generation's
`footprint.frame.world_xyz` to return to input units. The Blender adapter supplies
its own metric plane frame. Supported compound gable graphs use fixed-topology
covariance embedding; general convex quadrilaterals use the same solve/mesh
contracts. Unsupported incidence or failed convergence raises `UnsupportedRoofError`.

Proofs cover minimum certificates, independent small-polygon/exact-cover
oracles, hundreds of unknown connected-grid shapes, Cell coverage/provenance,
architectural ambiguity, graph disk incidence, seeded metamorphic invariance,
analytic planarity, frozen mesh/topology expectations, and Blender UV/material /
transform / atomic failure. `benchmark_generation.py` reports attempts and
unsupported counts separately; its exact-family fingerprints compare before
and after performance changes.

`audit_roof_support.py` separates the repeated six-fixture batch from 1000 unique
seeded connected-grid outlines. Full assignment diagnostics are streamed to
JSONL; summary incidence is nonexclusive. Sole known blockers censor downstream
failure and are upper bounds, not guaranteed support gains. Example:

```bash
python python/audit_roof_support.py --corpus python/out/support/corpus.json --output python/out/support/audit.json --details python/out/support/details.jsonl
```

`inspect_roof.py --fixture orthogonal_U` inspects all canonical retained
interpretations and the supported unified RoofGraph. `inspect_junctions.py`
inspects one fixed minimum partition/orientation only, so its rejection is not a
whole-footprint support verdict. See [relation audit and scope](docs/RELATION_TOPOLOGY_SUPPORT.md).


Staged fixed-corpus coverage and independent Blender conversion:

```bash
python python/audit_coverage.py --corpus python/docs/canonical/coverage_inputs_v1.json.gz --output python/out/coverage.json --details python/out/coverage.jsonl.gz
blender -b --factory-startup --python-exit-code 1 --python python/blender_audit_coverage.py -- --corpus python/docs/canonical/coverage_inputs_v1.json.gz --details python/out/coverage.jsonl.gz --output python/out/blender-coverage.json
blender -b --factory-startup --python-exit-code 1 --python python/blender_audit_coverage.py -- --zip packages/roof_generator-1.3.0.zip --corpus python/docs/canonical/coverage_inputs_v1.json.gz --details python/out/coverage.jsonl.gz --output python/out/blender-installed-coverage.json
python python/benchmark_roof_mesh.py --output python/out/core-budget.json
python python/profile_partitions.py --output python/out/partition-profile.json
```

Grid stress, nonuniform orthogonal, structured orthogonal, convex quad, structured
oblique and general polygon probe results are separate. The additional
`branch_network_inputs_v1.json.gz` proves separated terminal/middle operations.
See [current results](docs/END_TO_END_EVALUATION.md),
[solver contract](docs/SGA21_SOLVER.md), and
[nonorthogonal boundary](docs/NON_ORTHOGONAL.md).
