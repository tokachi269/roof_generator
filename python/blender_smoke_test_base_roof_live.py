# SPDX-License-Identifier: GPL-3.0-or-later
"""Run without -b: prove automatic roof updates in Blender's event loop."""

from pathlib import Path
import json
import sys
import time
import traceback

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
import roof_generator
from roof_generator.base_mesh import input_values, set_inputs

roof_generator.register()
assert bpy.ops.roof_generator.add_base_mesh(count=1, width=12, depth=6, max_cut=0, height=3, roof=True) == {"FINISHED"}
obj = bpy.context.object
probe = ROOT / "python/out/base_roofs/live_probe.blend"
probe.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(probe))
bpy.ops.wm.open_mainfile(filepath=str(probe))
obj = next(o for o in bpy.data.objects if o.get("building_base"))
if "--asset" in sys.argv:
    # A node-group asset added to an ordinary mesh has no operator-only tag.
    obj.pop("building_base", None)
modifier = obj.modifiers[0]
old_mesh = input_values(modifier)["Roof Mesh"].data
started = time.monotonic()
stage = 0
report = {"reopened_file": True, "untagged_asset": "--asset" in sys.argv}


def finish(error=None):
    output = ROOT / "python/out/base_roofs/live_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    report["error"] = error
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    bpy.ops.wm.quit_blender()


def check():
    global stage, old_mesh
    try:
        assert time.monotonic() - started < 30, "automatic update timed out"
        if stage == 0:
            set_inputs(modifier, **{"Width": 14, "Roof Pitch": 0.75})
            stage = 1
            return 0.1
        cache = input_values(modifier)["Roof Mesh"]
        if stage == 1:
            if cache.data == old_mesh:
                return 0.1
            assert json.loads(cache["building_base_key"]) == [14, 6, 0, 3, 2, 0, "Gable", 0.75]
            assert not obj.get("building_base_error")
            report["automatic_shape_pitch_update"] = "passed"
            old_mesh = cache.data
            set_inputs(modifier, **{"Height": 5})
            stage = 2
            return 0.1
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        try:
            assert mesh.polygons
            if stage == 2:
                assert abs(max(v.co.z for v in mesh.vertices) - 7.25) < 1e-5
                assert cache.data == old_mesh, "Height regenerated the roof"
                report["native_height_update"] = "passed"
            else:
                assert abs(max(v.co.z for v in mesh.vertices) - 5) < 1e-5
                assert cache.data == old_mesh, "Roof OFF regenerated the roof"
                report["native_roof_off"] = "passed"
        finally:
            evaluated.to_mesh_clear()
        if stage == 2:
            set_inputs(modifier, **{"Roof": False})
            stage = 3
            return 0.1
        finish()
    except Exception:
        finish(traceback.format_exc())
    return None


bpy.app.timers.register(check, first_interval=0.2)
