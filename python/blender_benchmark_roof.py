# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage/core/adapter timing on Blender's real generate_object route."""

import argparse
import json
from pathlib import Path
import sys
import subprocess
import time
from unittest.mock import patch

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "addon"))
from python.benchmark_roof import clear_caches, selected_cases, stage_times, stats, STAGES
# Load the source addon dependency directory before adapter imports.
from roof_generator.core import roof_geometry
from roof_generator import blender_output, mesh_input
import shapely


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=11)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--output", type=Path, default=ROOT / "python/out/harness/blender_performance.json")
    args = parser.parse_args(argv)
    if args.samples < 2 or args.warmup < 1:
        parser.error("Use at least two samples and one warmup")
    report = {"source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "blender": bpy.app.version_string, "python": sys.version.split()[0], "numpy": np.__version__, "shapely": shapely.__version__, "geos": shapely.geos_version_string, "samples": args.samples, "warmup": args.warmup, "profiled": False, "cases": {}}
    for case in selected_cases():
        data = bpy.data.meshes.new(case["name"])
        data.from_pydata([(x, y, 0) for x, y in case["footprint"]], [], [list(range(len(case["footprint"])))])
        obj = bpy.data.objects.new(case["name"], data)
        bpy.context.scene.collection.objects.link(obj)
        modes = {}
        for mode in ("cold_rebuild", "warm_partition"):
            clear_caches()
            rows = []
            for index in range(args.warmup + args.samples):
                if mode == "cold_rebuild":
                    clear_caches()
                original_core = mesh_input.generate_roof
                original_input = mesh_input.generate_footprint_mesh
                extra = {}

                def core(*params, **kwargs):
                    start = time.perf_counter()
                    result = original_core(*params, **kwargs)
                    extra["core_total"] = (time.perf_counter() - start) * 1000
                    return result

                def footprint(*params, **kwargs):
                    result = original_input(*params, **kwargs)
                    extra["mesh_creation_start"] = time.perf_counter()
                    return result

                with stage_times() as timings, patch.object(mesh_input, "generate_roof", core), patch.object(mesh_input, "generate_footprint_mesh", footprint):
                    start = time.perf_counter()
                    generated, result = blender_output.generate_object(obj, roof_type=case["roof_type"], pitch=case["pitch"], hide_source=False)
                    end = time.perf_counter()
                timings["total"] = (end - start) * 1000
                timings["core_total"] = extra["core_total"]
                timings["adapter_input"] = (extra["mesh_creation_start"] - start) * 1000 - extra["core_total"]
                timings["mesh_creation_uv_materials"] = (end - extra["mesh_creation_start"]) * 1000
                timings["core_orchestration"] = extra["core_total"] - sum(timings[name] for name in STAGES)
                if index >= args.warmup:
                    rows.append(timings)
                bpy.data.objects.remove(generated, do_unlink=True)
                bpy.data.orphans_purge(do_recursive=True)
            modes[mode] = {name: stats([row[name] for row in rows]) for name in rows[0]}
        report["cases"][case["name"]] = modes
        print(f"Blender {case['name']}: cold {modes['cold_rebuild']['total']['median_ms']:.2f}ms; warm {modes['warm_partition']['total']['median_ms']:.2f}ms", flush=True)
        bpy.data.objects.remove(obj, do_unlink=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
