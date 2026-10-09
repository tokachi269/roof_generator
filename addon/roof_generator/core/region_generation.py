# SPDX-License-Identifier: GPL-3.0-or-later
"""Declared polygon proposals to globally resolved, embedded roof candidates."""
from dataclasses import dataclass
from itertools import product

from .architecture import resolve
from .architecture_selection import symmetry_clusters
from .errors import UnsupportedRoofError
from .generation import GenerationSettings
from .region_architecture import interpret_regions
from .roof_ends import roof_configurations
from .roof_regions import parallel_recommendation
from .seed import choose, derive
from .solve import problem, solve
from .topology import compose
from .topology_candidates import validate_authority


@dataclass(frozen=True)
class RegionRoofCandidate:
    id: str
    architecture: object
    axes: tuple[int,...]
    composition: object
    geometry: object
    mesh: object
    recommendation: object
    ends: object

    def __post_init__(self):
        validate_authority(self.architecture,self.composition,self.geometry,self.axes)
        if self.mesh.graph != self.composition.graph:
            raise UnsupportedRoofError('region embedding changes roof topology')
        resolved=resolve(self.architecture,self.axes).with_ends(self.ends)
        decisions={j.cells:j.kind for j in resolved.ends.joints}
        for connection in self.composition.connections:
            pair=tuple(sorted((connection.host,connection.branch)))
            expected='shared' if connection.kind=='terminal' else 'extension'
            if decisions.get(pair)!=expected:
                raise UnsupportedRoofError('region connection contradicts resolved ends')

    @property
    def graph(self):return self.composition.graph


@dataclass(frozen=True)
class RegionRejection:
    region_id: str
    axes: tuple[int,...]
    stage: str
    reason: str


@dataclass(frozen=True)
class RegionChoice:
    region_id: str
    axes: tuple[int,...]
    end_choices: tuple
    recommendation: object


@dataclass(frozen=True)
class RegionPool:
    valid: tuple[RegionRoofCandidate,...]
    rejected: tuple[RegionRejection,...]
    complete: bool
    reason: str | None = None
    architectural: tuple[RegionChoice,...] = ()

    def inspect_ranking(self):
        known=tuple(c for c in self.architectural if c.recommendation.score is not None)
        best=max((c.recommendation.score for c in known),default=None)
        return {
            'architectural_assignments':len(self.architectural),
            'preferred_known_assignments':tuple(c for c in known if c.recommendation.score==best),
            'unscored_assignments':tuple(c for c in self.architectural if c.recommendation.score is None),
            'constructible_ids':tuple(c.id for c in self.valid),
            'selectable_ids':tuple(c.id for c in self.selectable()),
            'complete':self.complete,
            'selection_rule':'retain unknown priors and best known score among embedded candidates; then seed',
        }

    def selectable(self):
        if not self.complete:return ()
        known=tuple(c for c in self.valid if c.recommendation.score is not None)
        unknown=tuple(c for c in self.valid if c.recommendation.score is None)
        best=max((c.recommendation.score for c in known),default=None)
        return unknown+tuple(c for c in known if c.recommendation.score==best)

    def select(self,seed):
        if not self.complete or not self.valid:
            raise UnsupportedRoofError(self.reason or 'no valid embedded region roof candidate')
        # An unknown polygon/model prior is not a preferred zero score. Keep
        # that ambiguity observable rather than silently ordering it by None.
        return choose(self.selectable(),seed,'roof_candidate',key=lambda c:c.id)


@dataclass(frozen=True)
class RegionGeneration:
    footprint: object
    settings: GenerationSettings
    candidates: RegionPool
    selected: RegionRoofCandidate

    @property
    def geometry_problem(self):return self.selected.geometry


@dataclass(frozen=True)
class RegionRoof:
    generation: RegionGeneration
    mesh: object


def region_candidates(proposals,settings=GenerationSettings()):
    """All producers enter together. No runtime fallback or skeleton backend."""
    if settings.roof_type!='gable':
        raise UnsupportedRoofError('declared region model family currently supports gable only')
    proposals=tuple(proposals)
    if not proposals:
        raise UnsupportedRoofError('region generation needs explicit proposals')
    fp=proposals[0].footprint
    if any(p.footprint!=fp for p in proposals):
        raise UnsupportedRoofError('region proposals refer to different footprints')
    unique={p.id:p for p in proposals}
    valid={};rejected=[];choices=[];work=0
    def pool(complete,reason=None):
        return RegionPool(tuple(valid[k] for k in sorted(valid)),tuple(rejected),complete,reason,tuple(choices))
    for region_id in sorted(unique):
        proposal=unique[region_id]
        try:architecture=interpret_regions(proposal)
        except UnsupportedRoofError as exc:
            rejected.append(RegionRejection(region_id,(),'model',str(exc)));continue
        for axes in product(*(m.axes for m in architecture.members)):
            work+=1
            if work>settings.max_axis_assignments:
                return pool(False,'region model/end search budget exhausted')
            try:
                authority=resolve(architecture,axes)
                ends=tuple(roof_configurations(authority,symmetry_clusters(authority.analysis())))
                if not ends:
                    raise UnsupportedRoofError('global end constraints have no solution')
            except UnsupportedRoofError as exc:
                rejected.append(RegionRejection(region_id,axes,'ends',str(exc)));continue
            for index,configuration in enumerate(ends):
                if index:
                    work+=1
                    if work>settings.max_axis_assignments:
                        return pool(False,'region model/end search budget exhausted')
                stage='architecture'
                try:
                    resolved=authority.with_ends(configuration)
                    recommendation=parallel_recommendation(proposal,axes)
                    choices.append(RegionChoice(region_id,axes,
                        tuple((j.cells,j.kind) for j in configuration.joints),recommendation))
                    stage='composition';composition=compose(resolved)
                    stage='geometry_problem';geometry=problem(composition.graph,settings.pitch,settings.eave_height/fp.frame.scale)
                    stage='embedding';mesh=solve(composition.graph,geometry)
                    identity=derive(0,'region_roof_topology',(region_id,axes,
                        tuple((j.cells,j.kind) for j in configuration.joints)))
                    valid.setdefault(identity,RegionRoofCandidate(identity,resolved.architecture,axes,
                        composition,geometry,mesh,recommendation,configuration))
                except UnsupportedRoofError as exc:
                    rejected.append(RegionRejection(region_id,axes,stage,str(exc)))
    return pool(True)


def generate_region_roof(proposals,settings=GenerationSettings()):
    proposals=tuple(proposals)
    pool=region_candidates(proposals,settings)
    selected=pool.select(settings.seed)
    generation=RegionGeneration(proposals[0].footprint,settings,pool,selected)
    return RegionRoof(generation,selected.mesh)
