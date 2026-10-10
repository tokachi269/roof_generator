# SPDX-License-Identifier: GPL-3.0-or-later
"""Canonical roof models to explicit topology, fixed geometry and mesh."""

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING
from .footprint import analyze, Footprint
from .partition_candidates import candidates
from .architecture_selection import recommend, Recommendation, Policy
from .topology_candidates import TopologyCandidate, TopologyCandidates
from .solve import solve
from .mesh import RoofMesh
from .seed import derive
if TYPE_CHECKING:
    from .roof_candidates import RoofCandidates
    from .region_generation import RegionRoofCandidate
    from .polygon_generation import PolygonInterpretation, PolygonCandidates, PolygonCandidate


@dataclass(frozen=True)
class GenerationSettings:
    roof_type: str = "gable"
    pitch: float = 0.5
    eave_height: float = 0.0
    seed: int | str = 0
    reference_direction: tuple[float, float] = (1.0, 0.0)
    metres_per_unit: float = 1.0
    max_candidates: int = 4096
    max_work: int = 65536
    max_axis_assignments: int = 4096

    def __post_init__(self):
        if self.roof_type not in {"gable", "hip", "shed", "flat"}:
            raise ValueError("unsupported roof type")
        if (
            not math.isfinite(self.pitch)
            or self.pitch < 0
            or (self.roof_type != "flat" and self.pitch == 0)
            or not math.isfinite(self.eave_height)
        ):
            raise ValueError("positive finite pitch and finite eave height required")
        if (
            len(self.reference_direction) != 2
            or not all(math.isfinite(x) for x in self.reference_direction)
            or math.hypot(*self.reference_direction) == 0
        ):
            raise ValueError("reference direction must be a finite nonzero XY vector")
        if not math.isfinite(self.metres_per_unit) or self.metres_per_unit <= 0:
            raise ValueError("metres_per_unit must be positive and finite")
        if any(
            isinstance(x, bool) or not isinstance(x, int) or x < 1
            for x in (self.max_candidates, self.max_work, self.max_axis_assignments)
        ):
            raise ValueError("search budgets must be positive integers")
        derive(self.seed, "roof_candidate")


@dataclass(frozen=True)
class Generation:
    footprint: Footprint
    settings: GenerationSettings
    interpretation: "Recommendation | PolygonInterpretation"
    candidates: "TopologyCandidates | RoofCandidates | PolygonCandidates"
    selected: "TopologyCandidate | RegionRoofCandidate | PolygonCandidate"

    @property
    def geometry_problem(self):
        return self.selected.geometry


@dataclass(frozen=True)
class GeneratedRoof:
    generation: Generation
    mesh: RoofMesh


def prepare_generation(points, settings=GenerationSettings()):
    fp = analyze(points)
    if settings.roof_type=='hip' or (fp.orthogonal and settings.roof_type=='gable'):
        from .polygon_generation import candidates as polygon_candidates
        pool=polygon_candidates(fp,settings)
        return Generation(fp,settings,pool.interpretation,pool,pool.select(settings.seed))
    search = candidates(
        fp, max_candidates=settings.max_candidates, max_work=settings.max_work
    )
    # A pitched-roof evaluation is not a flat-roof prior. None retains the
    # minimum family without ranking; interpretation stays roof-independent.
    policy = (
        None
        if settings.roof_type == "flat"
        else Policy(metres_per_unit=settings.metres_per_unit)
    )
    interpretation = recommend(search, policy, defer_ranking=True)
    from .roof_candidates import roof_candidates
    pool = roof_candidates(fp,interpretation,settings)
    return Generation(fp, settings, interpretation, pool, pool.select(settings.seed))


def generate_roof(points, settings=GenerationSettings()):
    generation = prepare_generation(points, settings)
    from .roof_candidates import RoofCandidates
    from .polygon_generation import PolygonCandidates
    mesh = (generation.candidates.mesh(generation.selected)
            if isinstance(generation.candidates,(RoofCandidates,PolygonCandidates))
            else solve(generation.selected.graph, generation.geometry_problem))
    return GeneratedRoof(generation, mesh)
