# SPDX-License-Identifier: GPL-3.0-or-later
"""Observe canonical indexed mesh semantics; static data is the secondary oracle."""

from collections import Counter
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from roof_generator.core.generation import generate_roof, GenerationSettings

TOLERANCE = 5e-8


def cases():
    rows = json.loads((ROOT / "python/tests/fixtures/roof_acceptance.json").read_text())
    rows.append(dict(rows[0], name="rectangle_flat", roof_type="flat"))
    return rows


def ordered(values):
    if isinstance(values, (int, float)):
        return (round(float(values), 7),)
    result = []
    for x in values:
        result.extend(ordered(x))
    return tuple(result)


def cycle(points):
    ring = tuple(tuple(p) for p in points)
    return list(min((ring[i:] + ring[:i] for i in range(len(ring))), key=ordered))


def snapshot_mesh(footprint, mesh, *, rotation=None, translation=None):
    r = ((1, 0), (0, 1)) if rotation is None else rotation
    t = (0, 0) if translation is None else translation
    scale = footprint.frame.scale

    def undo(p):
        x, y = p[0] - t[0], p[1] - t[1]
        return (x * r[0][0] + y * r[1][0], x * r[0][1] + y * r[1][1])

    outline = tuple(undo(footprint.frame.world_xy(p)) for p in footprint.vertices)
    anchor = tuple(min(p[k] for p in outline) for k in (0, 1))

    def normalized(p):
        return tuple((p[k] - anchor[k]) / scale for k in (0, 1))

    vertices = tuple(
        (*normalized(undo(footprint.frame.world_xy(p[:2]))), p[2])
        for p in mesh.vertices
    )
    order = sorted(range(len(vertices)), key=lambda i: ordered(vertices[i]))
    ids = {v: i for i, v in enumerate(order)}
    faces = []
    for face in mesh.graph.faces:
        loop = tuple(ids[i] for i in face.loop)
        faces.append(
            {
                "loop": list(min(loop[i:] + loop[:i] for i in range(len(loop)))),
                "cells": list(face.cells),
            }
        )
    features = [
        {"vertices": sorted(ids[i] for i in e.vertices), "feature": e.kind}
        for e in mesh.graph.edges
    ]
    area = (
        sum(
            sum(
                vertices[a][0] * vertices[b][1] - vertices[b][0] * vertices[a][1]
                for a, b in zip(f.loop, f.loop[1:] + f.loop[:1])
            )
            / 2
            for f in mesh.graph.faces
        )
        * scale**2
    )
    perimeter = (
        sum(
            math.dist(vertices[e.vertices[0]][:2], vertices[e.vertices[1]][:2])
            for e in mesh.graph.edges
            if e.boundary is not None
        )
        * scale
    )
    return {
        "status": "ok",
        "normalized_footprint": cycle(tuple(normalized(p) for p in outline)),
        "vertices": [list(vertices[i]) for i in order],
        "faces": sorted(faces, key=lambda f: f["loop"]),
        "edge_features": sorted(features, key=lambda e: (e["vertices"], e["feature"])),
        "projected_area": area,
        "perimeter": perimeter,
    }


def snapshot(result, **transform):
    return snapshot_mesh(result.generation.footprint, result.mesh, **transform)


def capture(case):
    try:
        return snapshot(
            generate_roof(
                case["footprint"],
                GenerationSettings(
                    case["roof_type"], case.get("pitch", 0.5), seed=case.get("seed", 0)
                ),
            )
        )
    except ValueError as exc:
        return {"status": "unsupported", "failure_class": type(exc).__name__}


def differences(expected, actual, path="", *, limit=20):
    errors = []

    def visit(a, b, key):
        if len(errors) >= limit:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            if set(a) != set(b):
                errors.append(f"{key}: keys differ")
            for k in sorted(set(a) & set(b)):
                visit(a[k], b[k], key + "." + k)
        elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            if len(a) != len(b):
                errors.append(f"{key}: lengths differ")
            else:
                for i, (x, y) in enumerate(zip(a, b)):
                    visit(x, y, f"{key}[{i}]")
        elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
            tolerance = (
                0
                if isinstance(a, int) and isinstance(b, int)
                else TOLERANCE
                * (
                    max(1, abs(a), abs(b))
                    if key.endswith((".projected_area", ".perimeter"))
                    else 1
                )
            )
            if not math.isfinite(a) or not math.isfinite(b) or abs(a - b) > tolerance:
                errors.append(f"{key}: {a} != {b}")
        elif a != b:
            errors.append(f"{key}: values differ")

    visit(expected, actual, path)
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--output", type=Path, default=ROOT / "python/out/harness/semantic.json"
    )
    args = p.parse_args()
    data = {"cases": {c["name"]: capture(c) for c in cases()}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
