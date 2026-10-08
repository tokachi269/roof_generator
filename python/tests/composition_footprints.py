# SPDX-License-Identifier: GPL-3.0-or-later
"""Test-only unknown connected-grid buildings with separated narrow attachments."""

import random
from .grid_footprints import outline


def buildings(count=100, seed=4107):
    rng = random.Random(seed)
    for _ in range(count):
        width = rng.randrange(4, 9)
        parts = []
        x = rng.randrange(1, 4)
        for i in range(rng.randrange(1, 10)):
            branch_width = rng.randrange(1, width)
            parts.append(
                (x, x + branch_width, rng.randrange(2, 11), rng.choice((-1, 1)))
            )
            x += branch_width + rng.randrange(1, 5)
        # This generator's architectural domain is a longitudinal main ridge.
        # Square/fat receivers need a declared direction and are separately
        # tested as unsupported; this is not the unrestricted partition oracle.
        length = max(width + 1, x + rng.randrange(1, 4))
        cells = {(x, y) for x in range(length) for y in range(width)}
        for a, b, extension, side in parts:
            rows = (
                range(width, width + extension) if side == 1 else range(-extension, 0)
            )
            cells.update((x, y) for x in range(a, b) for y in rows)
        yield {
            "footprint": outline(cells),
            "body": (length, width),
            "branches": tuple(parts),
        }
