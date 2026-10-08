# Tools and verification

All tools use the distributable `roof_generator.core` under `addon/`.
Runtime needs Python's standard library. `requirements.txt` declares development
oracles only; Blender installs the ZIP without pip or external wheels.

```bash
python -m pip install -r python/requirements.txt
python -m unittest discover -s python/tests
python python/build_addon.py
python python/build_addon.py --check --output packages/roof_generator-1.2.0.zip
python python/inspect_rectangular_partition.py --help
python python/inspect_architectural_parts.py --help
python python/inspect_roof.py --fixture cross --seed 7 --output python/out/cross.json
python python/benchmark_generation.py --output python/out/performance.json
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test.py -- --zip packages/roof_generator-1.2.0.zip --output-dir python/out/addon
```

`inspect_roof.py` reports all validated alternatives, rejected assignments,
selected candidate and GeometryProblem. Its SVGs distinguish artificial cell
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
its own metric plane frame. Compound pitched graphs may have a GeometryProblem
without a supported mesh solve; `generate_roof` then raises `UnsupportedRoofError`.

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
