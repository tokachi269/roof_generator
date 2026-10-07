# SPDX-License-Identifier: GPL-3.0-or-later
"""Small semantic snapshot/differential tool; not an oracle for roof correctness."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "python/tests/fixtures/roof_acceptance.json"
TOLERANCE = 5e-8  # unit-perimeter coordinates and slope coefficients


def cases():
    result = json.loads(FIXTURES.read_text(encoding="utf-8"))
    quad = next(c for c in result if c["name"] == "general_convex_quad")
    result += [dict(quad, name=f"general_convex_quad_{kind}", roof_type=kind) for kind in ("flat", "hip", "shed")]
    shed = next(c for c in result if c["name"] == "rectangle_shed")
    result.append(dict(shed, name="rectangle_shed_cyclic_direction", footprint=shed["footprint"][2:] + shed["footprint"][:2]))
    result += [
        {"name": "invalid_self_crossing", "footprint": [[0, 0], [1, 1], [0, 1], [1, 0]], "roof_type": "gable", "pitch": 0.5},
        {"name": "invalid_duplicate_edge", "footprint": [[0, 0], [1, 0], [1, 0], [0, 1]], "roof_type": "gable", "pitch": 0.5},
        {"name": "invalid_zero_area", "footprint": [[0, 0], [1, 0], [2, 0]], "roof_type": "gable", "pitch": 0.5},
        {"name": "unsupported_gable_triangle", "footprint": [[0, 0], [8, 0], [2, 6]], "roof_type": "gable", "pitch": 0.5},
        {"name": "invalid_pitch", "footprint": [[0, 0], [12, 0], [12, 6], [0, 6]], "roof_type": "gable", "pitch": 0},
        dict(next(c for c in result if c["name"] == "orthogonal_L"), name="exhausted_search", max_states=1),
        dict(next(c for c in result if c["name"] == "orthogonal_T"), name="unsupported_height_step", overrides={"1": {"roof_type": "flat", "eave_height": 10}}),
    ]
    return result


def ordered(values):
    # Quantization is for order only. Keep original doubles for comparisons.
    return tuple(round(float(x), 7) for x in np.asarray(values).ravel())


def cycle(points):
    points = [list(map(float, p)) for p in points]
    if len(points) > 1 and np.linalg.norm(np.asarray(points[0]) - points[-1]) < 1e-12:
        points.pop()
    # Overlay can add arbitrary points on a straight region boundary.
    # Canonicalize that representation only, never mesh incidence or creases.
    while len(points) > 3:
        for i, point in enumerate(points):
            a, b = np.asarray(points[i - 1]), np.asarray(points[(i + 1) % len(points)])
            vector = b - a
            length2 = float(vector @ vector)
            if length2 == 0:
                continue
            t = float((np.asarray(point) - a) @ vector / length2)
            if 0 <= t <= 1 and np.linalg.norm(np.asarray(point) - a - t * vector) <= TOLERANCE / 10:
                points.pop(i)
                break
        else:
            break
    # Keep winding: reversing an upward face is a semantic difference.
    start = min(range(len(points)), key=lambda i: ordered(points[i:] + points[:i]))
    return points[start:] + points[:start]


def snapshot(result, *, rotation=None, translation=None):
    """Read output only, undo a known rigid transform, never recompute a roof.

    Unit-perimeter coordinates in reference axes avoid intrinsic-frame tie
    changes under cyclic/winding input permutations. IDs become geometry order.
    Original source IDs and intrinsic frame remain diagnostics, not equivalence.
    """
    rotation = np.eye(2) if rotation is None else np.asarray(rotation, float)
    translation = np.zeros(2) if translation is None else np.asarray(translation, float)
    frame = result.footprint.frame
    u = np.asarray(frame.u)
    basis = np.column_stack((u, [-u[1], u[0]]))
    scale = frame.scale

    def reference(points):
        return (np.asarray(points, float) - translation) @ rotation

    footprint_world = np.asarray(result.footprint.polygon.exterior.coords)[:-1] @ basis.T * scale + frame.origin
    footprint_reference = reference(footprint_world)
    anchor = footprint_reference.min(axis=0)

    def xy(points):
        world = np.asarray(points, float)[..., :2] @ basis.T * scale + frame.origin
        return (reference(world) - anchor) / scale

    def ring(polygon):
        return cycle(xy(np.asarray(polygon.exterior.coords)[:-1]))

    def segment(points):
        return sorted(xy(points).tolist(), key=ordered)

    def plane(coefficients):
        slope_world = basis @ np.asarray(coefficients[:2])
        c_world = coefficients[2] * scale - slope_world @ np.asarray(frame.origin)
        slope_reference = rotation.T @ slope_world
        c_reference = c_world + slope_world @ translation
        return [*map(float, slope_reference), float((c_reference + slope_reference @ anchor) / scale)]

    parts = sorted(result.topology.parts, key=lambda part: ordered(ring(part.footprint)))
    ids = {part.id: i for i, part in enumerate(parts)}
    input_ring = np.asarray(result.footprint.polygon.exterior.coords)[:-1]
    part_records = []
    for part in parts:
        sources = []
        for source in part.source_edges:
            i = source.footprint_edge
            sources.append({"segment": segment(source.segment), "footprint_segment": segment([input_ring[i], input_ring[(i + 1) % len(input_ring)]])})
        adjacency = [{"part": ids[n.part_id], "shared_boundary": sorted([segment(line) for line in n.shared_boundary], key=ordered)} for n in part.neighbors]
        part_records.append({
            "boundary": ring(part.footprint),
            "adjacency": sorted(adjacency, key=lambda item: item["part"]),
            "source_edges": sorted(sources, key=lambda item: ordered(item["segment"])),
            "planes": sorted([plane(p) for p in part.plane_definitions], key=ordered),
        })
    regions = []
    for region in result.topology.regions:
        regions.append({"boundary": ring(region.polygon), "holes": sorted([cycle(xy(np.asarray(hole.coords)[:-1])) for hole in region.polygon.interiors], key=ordered), "plane": plane(region.plane.coefficients), "parts": sorted(ids[i] for i in region.part_ids)})
    vertices = np.asarray(result.mesh.vertices)
    vertices = np.column_stack(((reference(vertices[:, :2]) - anchor) / scale, vertices[:, 2] / scale))
    vertex_order = sorted(range(len(vertices)), key=lambda i: ordered(vertices[i]))
    vertex_ids = {old: new for new, old in enumerate(vertex_order)}
    faces = []
    for face, owners in zip(result.mesh.faces, result.mesh.face_parts):
        indices = [vertex_ids[i] for i in face]
        start = indices.index(min(indices))
        faces.append({"loop": indices[start:] + indices[:start], "parts": sorted(ids[i] for i in owners)})
    edges = []
    incidence = Counter()
    for face in result.mesh.faces:
        for a, b in zip(face, face[1:] + face[:1]):
            incidence[tuple(sorted((a, b)))] += 1
    for edge, feature in result.mesh.edge_features.items():
        edges.append({"vertices": sorted(vertex_ids[i] for i in edge), "feature": feature})
    perimeter = sum(float(np.linalg.norm(vertices[b, :2] - vertices[a, :2])) * scale for (a, b), count in incidence.items() if count == 1)
    area = 0.0
    for face in result.mesh.faces:
        points = vertices[list(face), :2]
        area += float(np.sum(points[:, 0] * np.roll(points[:, 1], -1) - points[:, 1] * np.roll(points[:, 0], -1)) / 2) * scale**2
    return {
        "status": "ok", "normalized_footprint": cycle((footprint_reference - anchor) / scale),
        "part_count": len(parts), "parts": part_records,
        "regions": sorted(regions, key=lambda item: (ordered(item["plane"]), ordered(item["boundary"]))),
        "vertices": vertices[vertex_order].tolist(), "faces": sorted(faces, key=lambda item: item["loop"]),
        "edge_features": sorted(edges, key=lambda item: (item["vertices"], item["feature"])),
        "projected_area": area, "perimeter": perimeter,
        "diagnostics": {"intrinsic_footprint": [list(p) for p in input_ring], "source_original_ids": [[list(s.original_edges) for s in p.source_edges] for p in parts]},
    }


def differences(expected, actual, path="", *, limit=20):
    result = []

    def visit(a, b, key):
        if len(result) >= limit:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            ak, bk = set(a) - {"diagnostics"}, set(b) - {"diagnostics"}
            if ak != bk:
                result.append(f"{key}: keys differ {ak ^ bk}")
            for name in sorted(ak & bk):
                visit(a[name], b[name], key + "." + name)
        elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            if len(a) != len(b):
                result.append(f"{key}: length {len(a)} != {len(b)}")
            else:
                for i, (x, y) in enumerate(zip(a, b)):
                    visit(x, y, f"{key}[{i}]")
        elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
            # IDs/counts remain exact; metric area/perimeter get scaled tolerance.
            tolerance = TOLERANCE * max(1, abs(a), abs(b)) if key.endswith((".projected_area", ".perimeter")) else TOLERANCE
            if isinstance(a, int) and isinstance(b, int):
                tolerance = 0
            if not np.isfinite(a) or not np.isfinite(b) or abs(a - b) > tolerance:
                result.append(f"{key}: {a} != {b} (tol {tolerance})")
        elif a != b:
            result.append(f"{key}: {a!r} != {b!r}")

    visit(expected, actual, path)
    return result


def capture(case):
    from roof_generator.core.roof_building import generate_roof
    from roof_generator.core.roof_geometry import UnsupportedRoofError
    from roof_generator.core.roof_parts import RoofParameters

    try:
        result = generate_roof(case["footprint"], RoofParameters(case["roof_type"], pitch=case["pitch"]), max_states=case.get("max_states", 12000), part_parameters={int(i): RoofParameters(**params) for i, params in case.get("overrides", {}).items()})
    except UnsupportedRoofError as exc:
        return {"status": "unsupported", "failure_class": type(exc).__name__}
    return snapshot(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--addon-dir", type=Path, default=ROOT / "addon")
    parser.add_argument("--output", type=Path, default=ROOT / "python/out/harness/semantic.json")
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.addon_dir.resolve()))
    import shapely
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    document = {"schema": 1, "metadata": {"sha": sha, "python": sys.version.split()[0], "numpy": np.__version__, "shapely": shapely.__version__, "geos": shapely.geos_version_string, "oracle": "secondary regression baseline, not correctness proof"}, "cases": {case["name"]: capture(case) for case in cases()}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if args.reference:
        reference = json.loads(args.reference.read_text(encoding="utf-8"))
        errors = differences(reference["cases"], document["cases"])
        if errors:
            raise SystemExit("\n".join(errors))
    print(f"Semantic snapshots: {len(document['cases'])} cases; {args.output}")


if __name__ == "__main__":
    main()
