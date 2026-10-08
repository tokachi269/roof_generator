# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit unsupported generation; no alternate algorithm substitution."""


class UnsupportedRoofError(ValueError):
    """No graph in the explicitly supported composition scope exists."""
