# Architecture map

[Documentation index and current status](python/docs/README.md) is the entry point.
There are two deliberately separate generation systems:

| System | Code owner | Specification authority |
| --- | --- | --- |
| Packaged 1.5.0 addon | `addon/roof_generator/` | [Release contract](python/docs/current/README.md) |
| Unpackaged full-Line kernel | `python/roof_kernel/` | [Kernel contract](python/docs/ROOF_KERNEL_CONTRACT.md) |

The addon resolves models, constructs RoofGraph incidence, embeds fixed geometry,
then validates and exports a mesh. The kernel receives explicit boundary roles
and constructs source patches and coordinates together from wavefront events.
Blender adapters export decided structures; they do not repair topology or
substitute another model. Kernel proof meshes are not addon integration.

Detailed numerical and model contracts belong to their respective specifications,
not this map. Research and measured historical snapshots are indexed separately.
The [previous architecture snapshot](python/docs/history/ARCHITECTURE_62809e7.md)
preserves the superseded descriptions and their rationale.
