# Roof generation architecture

The canonical pipeline is:

```text
Footprint
  -> minimum rectangular partition candidates
  -> ArchitecturalPart interpretations
  -> valid RoofGraph candidates
  -> stable seeded selection
  -> GeometryProblem
  -> validated embedding
  -> ordinary mesh
  -> Blender object
```

The distributable `addon/roof_generator/core/` owns generation. Host tools import
the same modules. Blender reads evaluated planar footprints and creates mesh
objects; it does not choose or repair topology.

Footprint analysis validates a hole-free simple orthogonal polygon in its
intrinsic frame. Minimum partition uses good diagonals, bipartite matching,
maximum independent sets and reflex completion. Each alternative has the same
minimum certificate. Architectural interpretation keeps compound members,
consumed cuts, exterior provenance, local axis/receiver options and published
evaluation terms. Neither geometric Cell nor architectural unit implies one roof.

Topology composition consumes those member/port relations. It publishes only
complete disk graphs with boundary ownership, manifold links, roof-edge
semantics, a positive noncrossing drawing and a GeometryProblem. Rejected or
unimplemented relations are recorded separately. Incomplete candidate search
cannot select a winner. No algorithm substitutes for unsupported input.

Equivalent valid candidates are selected by stable namespaced seed digests and
geometry-based IDs. The orientation reference is a settings vector in the
footprint coordinate frame. Rotate it with the footprint for physical seed
equivariance, including perfectly symmetric shapes. Different random namespaces
do not consume a common PRNG stream.

Geometry solves fixed incidence; it cannot pick topology, roles or candidate
axes. Analytic rectangle embedding handles gable/hip/shed/flat. Compound topology
can be inspected as a GeometryProblem; nonlinear embedding support is a separate
capability and must fail explicitly until implemented. Mesh validation checks
fixed boundary, projection, shared vertices, positive faces and planarity.

Runtime core and Blender adapters require no external Python packages. Independent
development oracles may use NumPy/Shapely, declared separately from runtime.
See [the migration contract](python/docs/CANONICAL_MIGRATION.md) for the inventory
and [the research mapping](python/docs/ROOF_PART_INTERPRETATION_RESEARCH.md) for
published operations and their adaptation limits.
