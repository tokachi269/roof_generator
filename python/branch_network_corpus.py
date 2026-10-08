# SPDX-License-Identifier: GPL-3.0-or-later
"""Supplemental structured port corpus; names never enter production."""

import argparse
import gzip
import json
from pathlib import Path
import random


def corpus():
    rng = random.Random(69712)
    result = []
    for i in range(100):
        length = rng.uniform(40, 54)
        width = rng.uniform(4.5, 8)
        left = rng.uniform(3, 9)
        right = rng.uniform(3, 8) if i % 2 else 0
        branches = [(0, left, rng.uniform(max(10, left + 2), 16))]
        for position in (15, 27):
            w = rng.uniform(2.5, min(4, width - 1))
            branches.append((position, position + w, rng.uniform(7, 14)))
        if right:
            branches.append(
                (length - right, length, rng.uniform(max(10, right + 2), 16))
            )
        points = [(0, 0), (length, 0), (length, width)]
        for start, end, extension in reversed(branches):
            if points[-1] != (end, width):
                points.append((end, width))
            points.extend(
                ((end, width + extension), (start, width + extension), (start, width))
            )
        points.append((0, width))
        # Drop exact redundant boundary vertices before saving, no rectification.
        ring = []
        for p in points:
            if not ring or p != ring[-1]:
                ring.append(p)
        result.append({"name": f"branch_network_{i:03}", "footprint": ring})
    return {
        "version": 1,
        "seed": 69712,
        "corpora": {"structured_branch_network": result},
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.write_bytes(
        gzip.compress(
            (json.dumps(corpus(), separators=(",", ":")) + "\n").encode(), mtime=0
        )
    )
