# SPDX-License-Identifier: GPL-3.0-or-later
"""Actually convert each core-valid corpus roof; unattempted != Blender failure."""

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "addon"), str(ROOT / "python")]
from blender_smoke_test import source, validate
from roof_generator.blender_output import generate_objects, RoofRequest
from roof_generator.core.generation import GenerationSettings


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :]
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--details", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    corpus = json.loads(gzip.decompress(a.corpus.read_bytes()))["corpora"]
    inputs = {(c, r["name"]): r for c, records in corpus.items() for r in records}
    rows = []
    counts = Counter()
    attempts = Counter()
    for obj in tuple(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    with gzip.open(a.details, "rt") as f:
        for line in f:
            row = json.loads(line)
            if not row["success"]["mesh"]:
                continue
            category = row["corpus"]
            name = row["name"]
            attempts[category] += 1
            result = {"corpus": category, "name": name, "success": False}
            try:
                src = source(name, inputs[category, name]["footprint"])
                obj, data = generate_objects(
                    (RoofRequest(src, GenerationSettings(seed=0)),), hide_source=False
                )[0]
                validate(obj)
                result["success"] = True
                result["faces"] = len(obj.data.polygons)
                result["candidate"] = obj["roof_candidate_id"]
                counts[category] += 1
            except Exception as exc:
                result["reason"] = str(exc)
                result["failure_owner"] = "Blender"
            finally:
                for obj in tuple(bpy.data.objects):
                    bpy.data.objects.remove(obj, do_unlink=True)
                for data in tuple(bpy.data.meshes):
                    if not data.users:
                        bpy.data.meshes.remove(data)
            rows.append(result)
    output = {
        "blender": bpy.app.version_string,
        "seed": 0,
        "corpora": {
            c: {
                "attempted": attempts[c],
                "success": counts[c],
                "not_attempted": len(records) - attempts[c],
            }
            for c, records in corpus.items()
        },
        "cases": rows,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(output, indent=2) + "\n")
    print("STAGED_BLENDER_AUDIT", output["corpora"])


if __name__ == "__main__":
    main()
