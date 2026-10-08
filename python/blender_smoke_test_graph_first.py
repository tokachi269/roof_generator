# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual rectangle mesh export of the independent evaluation route."""

import argparse
import json
from pathlib import Path
import sys

import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "addon"))
from roof_generator.core.footprint import analyze
from roof_generator.core.cells import decompose
from roof_generator.core.topology import compose
from roof_generator.core.solve import solve_rectangle


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "python/out/graph-first-blender"
    )
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for obj in tuple(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    fixtures = json.loads(
        (ROOT / "python/tests/fixtures/roof_acceptance.json").read_text()
    )
    fixture = next(c for c in fixtures if c["name"] == "rectangle_gable")
    records = []
    for index, kind in enumerate(("gable", "hip", "shed", "flat")):
        fp = analyze(fixture["footprint"])
        graph = compose(decompose(fp), kind).graph
        result = solve_rectangle(graph, 0.5, 2 / fp.frame.scale)
        data = bpy.data.meshes.new("graph_first_" + kind)
        data.from_pydata(
            [fp.frame.world_xyz(p) for p in result.vertices], [], result.faces
        )
        data.update()
        if data.validate(verbose=True, clean_customdata=False):
            raise AssertionError("Blender detected invalid graph-first mesh")
        obj = bpy.data.objects.new(data.name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location.x = index * 18
        data.uv_layers.new(name="Roof UV")
        mat = bpy.data.materials.new(kind)
        data.materials.append(mat)
        bm = bmesh.new()
        bm.from_mesh(data)
        try:
            assert all(v.is_manifold for v in bm.verts)
            assert all(e.is_boundary or e.is_manifold for e in bm.edges)
            assert all(f.calc_area() > 1e-8 and f.normal.z > 0 for f in bm.faces)
        finally:
            bm.free()
        for old in bpy.context.selected_objects:
            old.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(island_margin=0.03)
        bpy.ops.object.mode_set(mode="OBJECT")
        assert any(abs(v.uv.x) + abs(v.uv.y) > 0 for v in data.uv_layers.active.data)
        records.append(
            {
                "roof_type": kind,
                "vertices": len(data.vertices),
                "faces": len(data.polygons),
                "uv": True,
                "material": True,
            }
        )
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_dir / "rectangle_roofs.blend"))
    (args.output_dir / "report.json").write_text(json.dumps(records, indent=2) + "\n")
    print("GRAPH_FIRST_RECTANGLE_SMOKE_OK")


if __name__ == "__main__":
    main()
