# SPDX-License-Identifier: GPL-3.0-or-later
"""Observe existing connection domains and difference topology without editing it."""

import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from roof_generator.core import roof_connections
from roof_generator.core.roof_building import generate_roof
from roof_generator.core.roof_parts import RoofParameters


def audit():
    fixtures = json.loads((ROOT / "python/tests/fixtures/roof_acceptance.json").read_text(encoding="utf-8"))
    report = {}
    original_patches = roof_connections.plane_patches
    original_difference = BaseGeometry.difference
    for case in fixtures:
        record = {"completed_domains": [], "difference_multipolygons": 0, "difference_hole_areas": []}

        def patches(solid):
            domain = solid.domain
            record["completed_domains"].append({"part": solid.part.id, "geometry": domain.geom_type, "nonconvex_area": domain.symmetric_difference(domain.convex_hull).area})
            return original_patches(solid)

        def difference(self, other, **kwargs):
            result = original_difference(self, other, **kwargs)
            if result.geom_type == "MultiPolygon":
                record["difference_multipolygons"] += 1
            polygons = [result] if result.geom_type == "Polygon" else getattr(result, "geoms", [])
            record["difference_hole_areas"].extend(Polygon(hole).area for p in polygons if p.geom_type == "Polygon" for hole in p.interiors)
            return result

        with patch.object(roof_connections, "plane_patches", patches), patch.object(BaseGeometry, "difference", difference):
            result = generate_roof(case["footprint"], RoofParameters(case["roof_type"], pitch=case["pitch"]))
        record["exposed_region_holes"] = sum(len(region.polygon.interiors) for region in result.topology.regions)
        report[case["name"]] = record
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "python/out/harness/overlay_audit.json")
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Overlay audit: {len(report)} fixtures; {args.output}")


if __name__ == "__main__":
    main()
