# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure complete roof generation for varied and repeated building footprints.

python python/benchmark_city.py --buildings 1000
blender -b --factory-startup --python-exit-code 1 --python python/benchmark_city.py -- --blender-objects --buildings 1000

Both modes use the public API with mandatory validation. Unique mode changes
aspect ratios; repeated mode reuses building templates at different positions.
Blender mode creates actual source and final mesh objects, UVs and materials.
"""

import argparse
import json
from pathlib import Path
import sys
import subprocess
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
sys.path.insert(0, str(ROOT / "python"))
from benchmark_roof import clear_caches, stats
from roof_generator.core.roof_building import generate_roof
from roof_generator.core.roof_parts import RoofParameters


def case_for(index, cases):
    position = index % 100
    if position < 70:
        name = (
            "rectangle_gable",
            "rectangle_hip",
            "rectangle_shed",
            "parallelogram",
            "trapezoid",
            "general_convex_quad",
            "rotated_rectangle",
        )[index % 7]
    elif position < 85:
        name = "orthogonal_L"
    elif position < 95:
        name = "orthogonal_T"
    elif position < 99:
        name = "orthogonal_U"
    else:
        name = "residential_multi_reflex"
    return cases[name]


def run(count, mode, *, blender_objects=False, out=None):
    import shapely

    if blender_objects:
        import bpy
        from roof_generator.blender_output import generate_objects, RoofRequest

        for obj in tuple(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.orphans_purge(do_recursive=True)
    cases = {
        c["name"]: c
        for c in json.loads(
            (ROOT / "python/tests/fixtures/roof_acceptance.json").read_text()
        )
    }
    clear_caches()
    samples, roofs, total_faces = [], [], 0
    requests = []
    started = time.perf_counter()
    for index in range(count):
        case = case_for(index, cases)
        footprint = np.asarray(case["footprint"], float)
        if mode == "unique_geometry":
            # Every input has a different aspect, rather than timing a cache
            # hit after applying an invariant uniform scale/rigid transform.
            footprint = footprint * [1 + 0.00021 * index, 1 + 0.00013 * index]
        pitch = 0.35 + 0.03 * (index % 9)
        if blender_objects:
            data = bpy.data.meshes.new(f"building_{index:04d}")
            data.from_pydata(
                [(x, y, 0) for x, y in footprint], [], [list(range(len(footprint)))]
            )
            source = bpy.data.objects.new(data.name, data)
            bpy.context.scene.collection.objects.link(source)
            source.location = ((index % 50) * 32, (index // 50) * 28, 3.2)
            requests.append(
                RoofRequest(source, RoofParameters(case["roof_type"], pitch=pitch))
            )
        else:
            footprint += [(index % 50) * 32, (index // 50) * 28]
            start = time.perf_counter()
            result = generate_roof(
                footprint, RoofParameters(case["roof_type"], pitch=pitch)
            )
            samples.append((time.perf_counter() - start) * 1000)
            total_faces += len(result.mesh.faces)
        if (index + 1) % 200 == 0:
            print(f"{mode}: {index + 1}/{count}", flush=True)
    if blender_objects:
        start = time.perf_counter()
        generated = generate_objects(requests)
        average = (time.perf_counter() - start) * 1000 / len(generated)
        roofs.extend(obj for obj, _ in generated)
        total_faces += sum(len(obj.data.polygons) for obj, _ in generated)
    elapsed = time.perf_counter() - started
    from roof_generator.core.roof_graph import _build_graph

    report = {
        "buildings": count,
        "mode": mode,
        "blender_objects": blender_objects,
        "latency_basis": (
            "batch duration / building count"
            if blender_objects
            else "individual core call"
        ),
        "batches": 1 if blender_objects else count,
        "total_seconds": elapsed,
        "roofs_per_second": count / elapsed,
        "generation": (
            {"average_per_roof_ms": average, "batch_ms": average * len(generated)}
            if blender_objects
            else stats(samples)
        ),
        "faces": total_faces,
        "graph_cache": _build_graph.cache_info()._asdict(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "shapely": shapely.__version__,
        "geos": shapely.geos_version_string,
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            ).strip()
        ),
    }
    if blender_objects:
        assert len(roofs) == count and all(
            o.type == "MESH" and o.data.uv_layers for o in roofs
        )
        report["blender"] = bpy.app.version_string
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=str(out / f"city_{mode}.blend"))
    print(
        f"{mode}: {elapsed:.2f}s, {report['roofs_per_second']:.1f} roofs/s; "
        + (
            f"batch average {average:.2f}ms/roof"
            if blender_objects
            else f"median {report['generation']['median_ms']:.2f}ms"
        ),
        flush=True,
    )
    return report


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--buildings", type=int, default=1000)
    parser.add_argument("--blender-objects", action="store_true")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "python/out/performance"
    )
    args = parser.parse_args(argv)
    if args.buildings < 1:
        parser.error("building count must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports = [
        run(
            args.buildings,
            mode,
            blender_objects=args.blender_objects,
            out=args.output_dir,
        )
        for mode in ("unique_geometry", "repeated_templates")
    ]
    name = "city_blender.json" if args.blender_objects else "city_core.json"
    (args.output_dir / name).write_text(json.dumps(reports, indent=2) + "\n")


if __name__ == "__main__":
    main()
