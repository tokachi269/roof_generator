# SPDX-License-Identifier: GPL-3.0-or-later
"""Unprofiled sample summaries shared by measurement tools."""

import statistics


def stats(samples):
    values = sorted(samples)
    index = 0.95 * (len(values) - 1)
    lo = int(index)
    hi = min(lo + 1, len(values) - 1)
    return {
        "median_ms": statistics.median(values),
        "p95_ms": values[lo] + (index - lo) * (values[hi] - values[lo]),
        "samples_ms": samples,
    }
