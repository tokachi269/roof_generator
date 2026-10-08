# SPDX-License-Identifier: GPL-3.0-or-later
"""Classical good-diagonal minimum rectangular partition; no roof decisions."""

from dataclasses import dataclass
import math
from .footprint import EPS, inside, on_segment, ray_hit, _intersects
from .graph import UnsupportedGraphError


@dataclass(frozen=True)
class Diagonal:
    endpoints: tuple[int, int]
    axis: int  # 0 horizontal, 1 vertical in the intrinsic frame


def good_diagonals(fp):
    """All open-interior reflex chords, via their first boundary hits.

    A farther boundary vertex cannot be a valid endpoint: the open chord would
    already touch the first one. This is enumeration, not partition selection.
    """
    if not fp.orthogonal:
        raise UnsupportedGraphError(
            "rectangle partition requires an orthogonal outline"
        )
    result = set()
    for start in fp.reflex:
        directions = (fp.directions[start - 1], tuple(-v for v in fp.directions[start]))
        for direction in directions:
            hit = ray_hit(fp.vertices, start, direction)
            if hit is None:
                continue
            point, _ = hit
            end = next(
                (i for i in fp.reflex if math.dist(fp.vertices[i], point) <= EPS), None
            )
            if end is None or start == end:
                continue
            a, b = fp.vertices[start], fp.vertices[end]
            if not inside(tuple((x + y) / 2 for x, y in zip(a, b)), fp.vertices):
                continue
            if any(
                on_segment(p, a, b)
                for i, p in enumerate(fp.vertices)
                if i not in (start, end)
            ):
                continue
            if any(
                _intersects(a, b, c, d)
                for i, (c, d) in enumerate(
                    zip(fp.vertices, fp.vertices[1:] + fp.vertices[:1])
                )
                if i not in (start, end)
                and (i + 1) % len(fp.vertices) not in (start, end)
            ):
                continue
            axis = int(abs(direction[1]) > abs(direction[0]))
            result.add(Diagonal(tuple(sorted((start, end))), axis))

    def key(diagonal):
        return diagonal.axis, tuple(
            sorted(
                tuple(round(x, 10) for x in fp.vertices[i]) for i in diagonal.endpoints
            )
        )

    return tuple(sorted(result, key=key))
