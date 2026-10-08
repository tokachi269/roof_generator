# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared source-boundary location and interval records."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundaryPoint:
    edge: int
    t: float


@dataclass(frozen=True)
class BoundarySpan:
    edge: int
    interval: tuple[float, float]
    original_edges: tuple[int, ...]
