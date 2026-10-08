# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned test inputs; grid stress is one category, not project coverage."""

import gzip
import json
import math
import random
from pathlib import Path
from inspect_architectural_parts import fixture

VERSION = 1
SEED = 382901
ROOT = Path(__file__).resolve().parents[1]


def corpora():
    rng = random.Random(SEED)
    grid = json.loads(
        gzip.decompress(
            (ROOT / "python/docs/canonical/support_grid.json.gz").read_bytes()
        )
    )
    result = {"orthogonal_grid_stress": grid}
    nonuniform = []
    for r in grid[:150]:
        xy = r["footprint"]
        maps = []
        for axis in (0, 1):
            coordinates = sorted({p[axis] for p in xy})
            value = 0.0
            mapping = {}
            for x in coordinates:
                mapping[x] = value
                value += rng.uniform(0.7, 7.5)
            maps.append(mapping)
        nonuniform.append(
            {
                "name": r["name"],
                "footprint": [[maps[k][p[k]] for k in (0, 1)] for p in xy],
            }
        )
    result["nonuniform_orthogonal"] = nonuniform
    structured = []
    for name in (
        "orthogonal_L",
        "orthogonal_T",
        "orthogonal_U",
        "cross",
        "staircase",
        "comb",
        "residential_multi_reflex",
        "grid_14",
        "grid_20",
        "grid_40",
    ):
        try:
            raw = fixture(name)["footprint"]
        except (FileNotFoundError, StopIteration, KeyError):
            from python.tests.grid_footprints import staircase, comb

            raw = staircase(5) if name == "staircase" else comb(5)
        for i in range(10):
            maps = []
            for axis in (0, 1):
                values = sorted({p[axis] for p in raw})
                value = 0.0
                mapping = {}
                for x in values:
                    mapping[x] = value
                    value += rng.uniform(1.5, 6.5)
                maps.append(mapping)
            structured.append(
                {
                    "name": f"{name}_{i}",
                    "footprint": [[maps[k][p[k]] for k in (0, 1)] for p in raw],
                }
            )
    acceptance = json.loads(
        (ROOT / "python/tests/fixtures/roof_acceptance.json").read_text()
    )
    structured += [
        r
        for r in acceptance
        if r["name"] in {"unequal_width_join", "terminating_ridge", "valley_join"}
    ]
    result["structured_orthogonal"] = structured
    quads = [
        r
        for r in acceptance
        if r["name"] in {"parallelogram", "trapezoid", "general_convex_quad"}
    ]
    for i in range(45):
        w, h = rng.uniform(9, 18), rng.uniform(4, 8)
        s = rng.uniform(-2, 2)
        kind = i % 3
        xy = (
            [(0, 0), (w, 0), (w + s, h), (s, h)]
            if kind == 0
            else [
                (0, 0),
                (w, 0),
                (w - 1 + s, h),
                (1 + s, h + (rng.uniform(-1, 1) if kind == 2 else 0)),
            ]
        )
        quads.append({"name": f"quad_{i}", "footprint": xy})
    result["convex_quadrilateral"] = quads
    oblique = [r for r in acceptance if r["name"] == "oblique_L"]
    # Affine changes are stress inputs, NEVER Euclidean equivalence oracles.
    for i, name in enumerate(("orthogonal_L", "orthogonal_T", "orthogonal_U") * 10):
        angle = rng.uniform(0.12, 0.65) * (-1 if i % 2 else 1)
        xy = fixture(name)["footprint"]
        oblique.append(
            {
                "name": f"angled_structure_{i}",
                "footprint": [(x + math.tan(angle) * y, y) for x, y in xy],
                "branch_angle_radians": math.pi / 2 - angle,
            }
        )
    # Tapered receivers and branches, not all affine/parallelogram inputs.
    for i in range(12):
        s = rng.uniform(-1.5, 1.5)
        oblique.append(
            {
                "name": f"tapered_branch_{i}",
                "footprint": [
                    (0, 0),
                    (16, 0),
                    (15, 5),
                    (10 + s, 5),
                    (11 + s, 12),
                    (6 + s, 12),
                    (6 + s, 5),
                    (1, 5),
                ],
            }
        )
    result["structured_oblique"] = oblique
    general = []
    for i in range(40):
        n = rng.randrange(5, 14)
        # Ordered radial samples have a simple boundary; alternate radii give
        # convex and concave probes without touching or intersection.
        points = []
        for j in range(n):
            a = 2 * math.pi * j / n
            radius = rng.uniform(4, 9)
            points.append((radius * math.cos(a), radius * math.sin(a)))
        general.append({"name": f"radial_{i}", "footprint": points})
    result["general_simple_polygon_probe"] = general
    return {"version": VERSION, "seed": SEED, "corpora": result}


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    payload = (json.dumps(corpora(), separators=(",", ":")) + "\n").encode()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(gzip.compress(payload, mtime=0))
    print({k: len(v) for k, v in corpora()["corpora"].items()})
