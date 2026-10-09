# SPDX-License-Identifier: GPL-3.0-or-later
"""Complete candidate families enter together; only embedded roofs are seeded."""
from dataclasses import dataclass
from .errors import UnsupportedRoofError,GenerationIssue
from .seed import choose
from .solve import solve
from .topology_candidates import build_candidates,Rejection,partition_id
from .receiver_regions import receiver_regions
from .region_architecture import interpret_receiver
from .region_generation import region_candidates,RegionPool


@dataclass(frozen=True)
class RoofCandidates:
    minimum: object
    regions: object
    valid: tuple
    rejected: tuple
    complete: bool
    reason: str | None
    constructible: tuple
    meshes: tuple

    @property
    def architectural(self):return self.minimum.architectural

    def select(self,seed=0):
        if not self.complete or not self.valid:
            details='; '.join(sorted({r.reason for r in self.rejected}))
            raise UnsupportedRoofError('no selectable roof candidate: '+(self.reason or details))
        return choose(self.valid,seed,'roof_candidate',key=lambda c:c.id)

    def mesh(self,candidate):
        return next(mesh for identity,mesh in self.meshes if identity==candidate.id)

    def inspect_ranking(self):
        return {'minimum_prior':self.minimum.inspect_ranking(),
                'region_prior':self.regions.inspect_ranking(),
                'constructible_candidate_ids':[c.id for c in self.constructible],
                'available_embedded_candidate_ids':[identity for identity,mesh in self.meshes],
                'selectable_candidate_ids':[c.id for c in self.valid] if self.complete else [],
                'complete':self.complete,
                'selection_rule':'best embedded minimum prior and admissible receiver models; canonical deduplication then seed',
                'prior_comparison':'full minimum Hu terms and partial region terms are not numerically compared'}


def roof_candidates(fp,interpretation,settings):
    if any(d.footprint!=fp for d in interpretation.search.candidates):
        raise UnsupportedRoofError('candidate sources refer to different footprints')
    minimum=build_candidates(interpretation,settings.roof_type,
        reference_direction=settings.reference_direction,pitch=settings.pitch,
        eave_height=settings.eave_height,max_axis_assignments=settings.max_axis_assignments)
    if not fp.orthogonal or settings.roof_type!='gable':return minimum
    # Every producer runs independently of another producer's success. An
    # incomplete family invalidates selection; it is never runtime fallback.
    search=receiver_regions(fp,max_work=settings.max_work,max_candidates=settings.max_candidates,
                            provenance=interpretation.search.candidates[0] if interpretation.search.candidates else None)
    regions=(region_candidates(search.proposals,settings,model=interpret_receiver)
             if search.proposals else RegionPool((),(),True))
    complete=minimum.complete and search.complete and regions.complete
    reason=next((x for x in (minimum.reason if not minimum.complete else None,
                             search.reason,regions.reason) if x),None)
    rejected=list(minimum.rejected)
    rejected.extend(Rejection(r.region_id,r.axes,r.reason,
                    (GenerationIssue(r.stage,'region_candidate'),)) for r in regions.rejected)
    embedded={};meshes={}
    for candidate in minimum.constructible:
        try:
            meshes[candidate.id]=solve(candidate.graph,candidate.geometry)
            embedded[candidate.id]=candidate
        except UnsupportedRoofError as exc:
            rejected.append(Rejection(partition_id(candidate.architecture.decomposition,settings.reference_direction),
                                      candidate.axes,str(exc),
                                      (GenerationIssue('embedding','unsupported'),)))
    best=max((c.score for c in embedded.values()),default=None)
    selectable={c.id:c for c in embedded.values() if c.score==best}
    # Equivalent model/support/topology identity gets one probability mass.
    # The full minimum prior remains the metadata representative of aliases.
    minimum_ids=set(embedded)
    for candidate in regions.valid:
        if candidate.id not in embedded:
            embedded[candidate.id]=candidate;meshes[candidate.id]=candidate.mesh
    for candidate in regions.selectable():
        if candidate.id not in minimum_ids:selectable[candidate.id]=candidate
    if len(embedded)>settings.max_candidates:
        complete=False;reason='combined roof candidate budget exhausted'
    constructed={c.id:c for c in minimum.constructible}
    constructed.update({c.id:c for c in regions.valid})
    return RoofCandidates(minimum,regions,tuple(selectable[k] for k in sorted(selectable)),
        tuple(rejected),complete,reason,tuple(constructed[k] for k in sorted(constructed)),
        tuple((k,meshes[k]) for k in sorted(meshes)))
