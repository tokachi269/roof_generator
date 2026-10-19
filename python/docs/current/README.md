# Packaged addon contract (1.5.0)

Authority for the distributable `packages/roof_generator-1.5.0.zip`, checked
against `addon/roof_generator/__init__.py` and `core/generation.py` at `62809e7`.
The separate `python/roof_kernel/` implementation is not shipped in this ZIP.
The [documentation index](../README.md) owns the cross-system status and next gates.

## Input and supported model domains

Input is a filled planar mesh with a simple, hole-free perimeter. Touching,
self-intersecting, nonfinite and nonplanar inputs fail explicitly. Rigid rotation,
translation and object scale are handled through the footprint/adapter frame.

| Requested type / input | Declared construction domain |
| --- | --- |
| Gable, orthogonal simple polygon | Minimum/receiver rectangle analysis guides exterior end choices; the physical roof support is one polygon. A completed roof can retain hip facets. |
| Hip, simple polygon at arbitrary angles | All exterior edges are EAVEs; global bounded polygon incidence. |
| Gable, nonorthogonal compound | Opposed-support triangular terminal caps; all maximal compatible admitted sets, with remaining exterior EAVEs. |
| Gable or shed, convex nonorthogonal quadrilateral | Existing single-quad primitive domain, including nonparallel eaves. |
| Shed, rectangle | Analytic primitive. Compound shed is unsupported. |
| Flat, orthogonal simple polygon or convex quadrilateral | One planar roof surface, without a pitched-roof ranking prior. |

These are model domains, not a universal-success claim for the bundled event
implementation. No eligible terminal gable does not authorize a hip substitute.
Nonterminal, partial-edge and genuinely nonparallel-support compound gables,
holes and general compound shed remain outside this release. See
[angle model details](../ARBITRARY_ANGLE_ROOFS.md) and
[partition analysis](../MINIMUM_RECTANGULAR_PARTITION.md).

## Generation and authority

`generate_roof(points, GenerationSettings(...))` and `prepare_generation` are the
public core entry points. Dispatch follows declared input and requested roof type:

```text
Footprint -> model and complete candidate family -> RoofGraph + GeometryProblem
          -> fixed embedding + mesh validation -> completed pool -> seed -> mesh
```

`generation.uses_polygon_model` sends every hip, every orthogonal gable and
non-quad/concave nonorthogonal gables through `polygon_generation`. The other
supported flat/shed/quad domains use the restricted partition/architecture route.
There is no retry between those routes after failure.

`PolygonRoof` owns physical support and explicit exterior gable edges. Rectangle
cuts are analysis/provenance, not independent completed roofs. `roof_intent` and
`roof_preference` own end domains and axis preference; `wavefront` bounds bundled
ordinary-skeleton incidence; `polygon_roof` owns terminal-cap disk replacement
and final indexed incidence. Partial/interfering caps are not guessed.

All candidate models must finish their declared searches before selection.
Stable geometry-based IDs and namespaced seed digests choose among validated
alternatives. Seed cannot repair an unsupported operation or select an incomplete
prefix. Rotate the explicit reference direction with the coordinate input for
physical equivariance, including symmetric footprints.

## Coordinates, mesh and Blender

`GeometryProblem` freezes incidence, variables, boundary/height anchors, ridge
directions and slope planes. `solve.embed` uses anchored analytic primitives,
then [linear embedding](../PLANE_EMBEDDING.md) when planes are complete, otherwise
the [covariance solver](../SGA21_SOLVER.md). This is constraint-based dispatch;
geometry cannot discover a different roof or retopologize a failed one.

Mesh validation preserves face cycles and checks planarity, positive projection,
shared incidence, noncrossing and fixed boundary. Blender exports ordinary mesh
objects, UVs, materials and provenance. Batch conversion validates before scene
mutation. Native Geometry Nodes bases keep their walls/base visible if the
canonical Python roof update fails; the roof backend itself is not a GN graph.

Runtime is Blender plus the Python standard library. NumPy/Shapely are independent
development oracles. Installation and UI controls are in the root README.

## Evidence and limits

Versioned measurements are reports, not this contract. Read
[1.5.0 angle evaluation](../history/ARBITRARY_ANGLE_EVALUATION.md),
[embedding evaluation](../history/PLANE_EMBEDDING_EVALUATION.md) and
[the older polygon migration](../POLYGON_ROOF_RELEASE.md) with their recorded
revisions. Older restricted-grammar coverage does not describe this release.
Finite corpora and installed-addon smoke do not imply universal coverage or a
hard latency guarantee. Package installation, standalone kernel export and actual
Blender scene validation are separate observations.
