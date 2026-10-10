# SPDX-License-Identifier: GPL-3.0-or-later
"""Polygon support and resolved ends to complete, embedded, seeded roofs."""
from dataclasses import asdict, dataclass
import json

from .cells import decompose
from .errors import UnsupportedRoofError, GenerationIssue
from .member_layout import member_layout
from .polygon_roof import PolygonRoof, topology
from .receiver_regions import receiver_regions
from .roof_intent import RoofIntent, cap_domain, terminal_configurations, TerminalDomain, opposed_supports
from .roof_preference import recommend
from .roof_regions import minimum_regions
from .seed import choose, derive, point_identity
from .solve import problem, solve
from .wavefront import wavefront
from .constraints import check_planes


@dataclass(frozen=True)
class Guide:
    proposal: object
    axes: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class PolygonTopology:
    id: str
    architecture: PolygonRoof
    guides: tuple[Guide, ...]
    graph: object
    geometry: object

    def __post_init__(self):
        fp=self.architecture.footprint
        if self.graph.outline!=fp.vertices or self.graph.source_edges!=fp.source_edges or \
           self.geometry.faces!=tuple(f.loop for f in self.graph.faces) or \
           self.graph.roof_type!=self.architecture.roof_type:
            raise UnsupportedRoofError('polygon geometry contradicts resolved support')
        for edge in self.graph.edges:
            if edge.boundary is not None:
                expected='gable_end' if edge.boundary.edge in self.architecture.gable_edges else 'eave'
                if edge.kind!=expected:
                    raise UnsupportedRoofError('polygon graph contradicts resolved roof ends')

    def inspect_features(self):
        return tuple({'vertices':e.vertices,'kind':e.kind,'region':0,
                      'source_eaves':tuple(self.graph.faces[i].eaves for i in e.faces),
                      'operation':'global source-facet incidence'}
                     for e in self.graph.edges if e.boundary is None)


@dataclass(frozen=True)
class PolygonCandidate(PolygonTopology):
    mesh: object

    def __post_init__(self):
        super().__post_init__()
        if self.mesh.graph is not self.graph:
            raise UnsupportedRoofError('polygon embedding changes resolved topology')


@dataclass(frozen=True)
class PolygonRejection:
    stage: str
    reason: str
    gable_edges: tuple[int, ...] = ()


@dataclass(frozen=True)
class PolygonInterpretation:
    footprint: object
    guides: tuple
    models: tuple[PolygonRoof, ...]
    terminal_domain: TerminalDomain | None = None

    def inspect(self):
        result={'support':self.footprint.vertices,
                'guides':[p.inspect() for p in self.guides],
                'resolved_models':[m.inspect() for m in self.models],
                'authority':'whole polygon models and explicit exterior ends'}
        if self.terminal_domain is not None:
            result['terminal_domain']=asdict(self.terminal_domain)
        return result


@dataclass(frozen=True)
class PolygonCandidates:
    interpretation: PolygonInterpretation
    valid: tuple[PolygonCandidate, ...]
    rejected: tuple[PolygonRejection, ...]
    complete: bool
    reason: str | None
    work: int
    constructible: tuple[PolygonTopology, ...]

    def select(self, seed):
        if not self.complete or not self.valid:
            raise UnsupportedRoofError(self.reason or 'no compatible polygon roof',
                issues=(GenerationIssue('architecture','polygon_incomplete' if not self.complete else 'polygon_unsupported'),))
        return choose(self.valid,seed,'roof_candidate',key=lambda c:c.id)

    def mesh(self, candidate):
        return next(c.mesh for c in self.valid if c.id==candidate.id)

    def inspect_ranking(self):
        return {'complete':self.complete,'reason':self.reason,
                'proposal_sources':[p.inspect() for p in self.interpretation.guides],
                'constructible_candidate_ids':[c.id for c in self.constructible],
                'available_embedded_candidate_ids':[c.id for c in self.valid],
                'selectable_candidate_ids':[c.id for c in self.valid] if self.complete else [],
                'selection_rule':('soft componentwise long-axis preference; maximal compatible gable ends per model; deduplicate then seed'
                                  if self.interpretation.guides else
                                  'all-eave hip or maximal opposed-support terminal sets; validated then seed'),
                'scope':'continuous polygon roof; exterior intent is not independent Cell roof parts'}


def candidates(fp, settings):
    incidence=wavefront(fp,max_work=settings.max_work)
    if settings.roof_type=='hip':
        interpretation=PolygonInterpretation(fp,(),(PolygonRoof(fp,(),'hip'),))
        return _embed_models(interpretation,incidence,settings,{():[]},{},work=incidence.work)
    available,conflicts,blocked=cap_domain(fp,incidence)
    if not fp.orthogonal:
        domain=TerminalDomain(tuple(e for e in range(len(fp.vertices)) if opposed_supports(fp,e)),
                              available,conflicts,blocked)
        remaining=settings.max_work-incidence.work
        if remaining<1:
            return PolygonCandidates(PolygonInterpretation(fp,(),(),domain),(),(),False,
                                     'combined polygon work budget exhausted',incidence.work,())
        pool=terminal_configurations(available,conflicts,blocked,max_work=remaining,
                                     max_candidates=settings.max_candidates)
        models=tuple(PolygonRoof(fp,c.selected) for c in pool.configurations)
        interpretation=PolygonInterpretation(fp,(),models,domain)
        result=_embed_models(interpretation,incidence,settings,{m.gable_edges:[] for m in models},{},
                            complete=pool.complete,reason=pool.reason,work=incidence.work+pool.work)
        if pool.complete and not models:
            rejected=(PolygonRejection('architecture','no opposed-support terminal gable cap'),)
            return PolygonCandidates(interpretation,(),rejected,True,rejected[0].reason,result.work,())
        return result
    decomposition=decompose(fp)
    minimum=minimum_regions(decomposition)
    receiver=receiver_regions(fp,max_work=settings.max_work,max_candidates=settings.max_candidates,
                              provenance=decomposition)
    proposals=(minimum,*receiver.proposals) if receiver.complete else (minimum,)
    complete=receiver.complete;reason=receiver.reason;work=incidence.work
    layouts={p.id:member_layout(p) for p in proposals}
    configurations={}
    # Every source enters before any construction; incomplete sources forbid
    # seed selection even if another source produces a verified roof.
    for proposal in proposals:
        remaining=settings.max_work-work
        if remaining<=0:
            complete=False;reason='combined polygon architecture work budget exhausted';break
        pool=recommend(layouts[proposal.id],available,conflicts,blocked,max_work=remaining)
        work+=pool.work
        if not pool.complete:
            complete=False;reason=pool.reason;continue
        for option in pool.configurations:
            configurations.setdefault(option.selected,[]).append(Guide(proposal,option.axis_domains))
        if len(configurations)>settings.max_candidates:
            complete=False;reason='polygon roof candidate budget exhausted';break
    models=tuple(PolygonRoof(fp,ends) for ends in sorted(configurations))
    interpretation=PolygonInterpretation(fp,proposals,models)
    return _embed_models(interpretation,incidence,settings,configurations,layouts,
                         complete=complete,reason=reason,work=work)


def _embed_models(interpretation, incidence, settings, configurations, layouts, *,
                  complete=True, reason=None, work=0):
    """One publisher validates every resolved polygon model before seed selection."""
    fp=interpretation.footprint
    identity=point_identity(fp,settings.reference_direction)
    outline=tuple(identity(p) for p in fp.vertices);valid=[];constructed=[];rejected=[]
    for model in interpretation.models:
        ends=model.gable_edges;aliases=configurations[ends]
        stage='topology'
        try:
            if aliases:
                guide=min(aliases,key=lambda g:(g.proposal.id,g.proposal.source,g.axes))
                intent=RoofIntent.from_caps(layouts[guide.proposal.id],tuple(a[0] for a in guide.axes),ends)
            graph,_=topology(model,incidence)
            if aliases:intent.verify(graph)
            stage='geometry_problem';geometry=problem(graph,settings.pitch,settings.eave_height/fp.frame.scale)
            boundary=tuple(sorted(tuple(sorted((outline[e],outline[(e+1)%len(outline)]))) for e in ends))
            namespace='global_roof' if model.roof_type=='gable' else 'global_roof_hip'
            code=derive(0,namespace,json.dumps((tuple(sorted(outline)),boundary)))
            constructed.append(PolygonTopology(code,model,tuple(aliases),graph,geometry))
            stage='embedding';check_planes(geometry);mesh=solve(graph,geometry)
            valid.append(PolygonCandidate(code,model,tuple(aliases),graph,geometry,mesh))
        except UnsupportedRoofError as exc:
            rejected.append(PolygonRejection(stage,str(exc),ends))
    return PolygonCandidates(interpretation,tuple(sorted(valid,key=lambda c:c.id)),tuple(rejected),complete,reason,work,tuple(constructed))
