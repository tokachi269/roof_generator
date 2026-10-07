# SPDX-License-Identifier: GPL-3.0-or-later
"""Unprofiled stage timings of the actual public generation route."""

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NAMES = (
    "rectangle_gable",
    "orthogonal_L",
    "orthogonal_T",
    "orthogonal_U",
    "residential_multi_reflex",
    "oblique_L",
    "general_convex_quad",
)
STAGES = ("normalize", "decompose", "connect", "tessellate", "validate")


def clear_caches():
    from roof_generator.core import (
        roof_geometry,
        roof_parts,
        roof_partition,
        roof_graph,
    )

    for name in (
        "polygon_ring",
        "reflex_vertices",
        "ring_key",
        "properties",
        "bounding_aspect",
    ):
        getattr(roof_geometry, name).cache_clear()
    roof_parts._partition.cache_clear()
    roof_partition._reflex_vertices.cache_clear()
    roof_graph._build_graph.cache_clear()


@contextmanager
def stage_times():
    """Instrument existing orchestration references, no copied production pipeline."""
    from contextlib import ExitStack
    from roof_generator.core import roof_building

    values = dict.fromkeys(STAGES, 0.0)
    names = (
        "normalize_footprint",
        "decompose",
        "connect",
        "tessellate",
        "validate_mesh",
    )

    def measure(original, stage):
        def wrapped(*args, **kwargs):
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                values[stage] += (time.perf_counter() - start) * 1000

        return wrapped

    with ExitStack() as stack:
        for stage, name in zip(STAGES, names):
            stack.enter_context(
                patch.object(
                    roof_building, name, measure(getattr(roof_building, name), stage)
                )
            )
        yield values


def stats(samples):
    return {
        "median_ms": float(np.median(samples)),
        "p95_ms": float(np.percentile(samples, 95)),
        "samples_ms": samples,
    }


def selected_cases():
    fixtures = json.loads(
        (ROOT / "python/tests/fixtures/roof_acceptance.json").read_text(
            encoding="utf-8"
        )
    )
    return [next(c for c in fixtures if c["name"] == name) for name in NAMES]


def benchmark(*, samples=11, warmup=2):
    from roof_generator.core.roof_building import generate_roof
    from roof_generator.core.roof_parts import RoofParameters
    import shapely

    report = {
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            ).strip()
        ),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
            "shapely": shapely.__version__,
            "geos": shapely.geos_version_string,
        },
        "samples": samples,
        "warmup": warmup,
        "profiled": False,
        "cases": {},
    }
    for case in selected_cases():
        modes = {}
        for mode in ("cold_rebuild", "warm_partition"):
            clear_caches()
            rows = []
            for index in range(warmup + samples):
                if mode == "cold_rebuild":
                    clear_caches()  # outside timing, including after warmup
                with stage_times() as timings:
                    start = time.perf_counter()
                    result = generate_roof(
                        case["footprint"],
                        RoofParameters(case["roof_type"], pitch=case["pitch"]),
                    )
                    timings["total"] = (time.perf_counter() - start) * 1000
                timings["orchestration"] = timings["total"] - sum(
                    timings[stage] for stage in STAGES
                )
                if index >= warmup:
                    rows.append(timings)
            modes[mode] = {
                name: stats([row[name] for row in rows])
                for name in (*STAGES, "orchestration", "total")
            }
            modes[mode]["searched_states"] = result.decomposition.searched_states
            modes[mode]["parts"] = len(result.decomposition.parts)
        report["cases"][case["name"]] = modes
        print(
            f"{case['name']}: cold {modes['cold_rebuild']['total']['median_ms']:.2f}ms; warm {modes['warm_partition']['total']['median_ms']:.2f}ms",
            flush=True,
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "python/out/harness/performance.json"
    )
    parser.add_argument("--samples", type=int, default=11)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument(
        "--profile",
        type=Path,
        help="Separate diagnostic cProfile, never used as benchmark timings",
    )
    args = parser.parse_args()
    if args.samples < 2 or args.warmup < 1:
        parser.error("Use at least two samples and one warmup")
    sys.path.insert(0, str(ROOT / "addon"))
    report = benchmark(samples=args.samples, warmup=args.warmup)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.profile:
        import cProfile
        from roof_generator.core.roof_building import generate_roof

        case = next(
            c for c in selected_cases() if c["name"] == "residential_multi_reflex"
        )
        clear_caches()
        profiler = cProfile.Profile()
        profiler.runcall(generate_roof, case["footprint"])
        args.profile.parent.mkdir(parents=True, exist_ok=True)
        profiler.dump_stats(str(args.profile))


if __name__ == "__main__":
    main()
