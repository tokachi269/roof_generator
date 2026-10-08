# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit unsupported generation; no alternate algorithm substitution."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationIssue:
    stage: str
    code: str
    cells: tuple[int, ...] = ()


class UnsupportedRoofError(ValueError):
    """No graph in the explicitly supported composition scope exists."""

    def __init__(self, message="", *, issues=()):
        super().__init__(message)
        self.issues = tuple(issues)
