# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate one editable roof object from a filled planar footprint mesh.

Run in Blender's Text Editor (edit the constants) or use the CLI arguments.
Uses the addon's validated roof generation and mesh output API.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
OBJECT_NAME = None
ROOF_TYPE = "gable"
PITCH = 0.5  # rise/run; tan(pitch angle)
EAVE_HEIGHT = 0.0  # offset along footprint normal, in world units
DEBUG_PARTS = False

# The addon is the single owner of final Blender conversion.
ADDON_DIR = SCRIPT_DIR.parent / "addon"
if str(ADDON_DIR) not in sys.path:
    sys.path.insert(0, str(ADDON_DIR))
from roof_generator.blender_output import generate_object


def main():
    import bpy

    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--object-name", default=OBJECT_NAME)
    parser.add_argument("--mesh-name", default=None)
    parser.add_argument(
        "--roof-type", choices=["flat", "gable", "hip", "shed"], default=ROOF_TYPE
    )
    parser.add_argument("--pitch", type=float, default=PITCH)
    parser.add_argument("--eave-height", type=float, default=EAVE_HEIGHT)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--debug-cells", action="store_true", default=DEBUG_PARTS)
    args = parser.parse_args(argv)
    source = (
        bpy.data.objects.get(args.object_name)
        if args.object_name
        else bpy.context.active_object
    )
    obj, result = generate_object(
        source,
        roof_type=args.roof_type,
        pitch=args.pitch,
        eave_height=args.eave_height,
        seed=args.seed,
        mesh_name=args.mesh_name,
        debug_cells=args.debug_cells,
    )
    print(
        json.dumps(
            {
                "object": obj.name,
                "vertices": len(obj.data.vertices),
                "faces": len(obj.data.polygons),
                "candidate": result.roof.generation.selected.id,
                "seed": args.seed,
                "features": {
                    kind: sum(e.kind == kind for e in result.roof.mesh.graph.edges)
                    for kind in {e.kind for e in result.roof.mesh.graph.edges}
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
