# SPDX-License-Identifier: GPL-3.0-or-later
"""Architectural axis preference followed by compatible global gable ends.

Long ridge axes are a prior, not a construction prohibition. Candidate end
sets and their axis domains are enumerated together before embedding. Prefer
the componentwise-minimal sets of transverse members, then retain every
maximal compatible gable-end set for each surviving axis model. Incomparable
interpretations survive. No numeric length/area/feature-count score, sequential
fallback, seed choice or geometry-dependent ranking.

This isolated cap-domain producer does not fulfill nonterminal gable intent
and is not a weighted wavefront backend or an addon production migration.
"""
from itertools import combinations

from .roof_intent import RoofIntent, CapPool, gable_configurations


def recommend(layout, available, conflicts=(), blocked=(), *, max_work=65536):
    from roof_generator.core.footprint import EPS
    if max_work<1:raise ValueError('positive architecture work budget required')
    long=[]
    for region in layout.candidate.regions:
        size=tuple(max(p[k] for p in region.boundary)-min(p[k] for p in region.boundary)
                   for k in (0,1))
        long.append((0,1) if abs(size[0]-size[1])<=4*EPS
                    else (0 if size[0]>size[1] else 1,))
    available=tuple(sorted(set(available)-set(blocked)))
    frontier=set();work=0
    for count in range(1,len(available)+1):
        for selected in combinations(available,count):
            work+=1
            if work>max_work:return CapPool((),False,work,'axis preference work budget exhausted')
            if any(a in selected and b in selected for a,b in conflicts):continue
            domains=RoofIntent.axis_domains(layout,selected)
            if not all(domains):continue
            transverse=frozenset(i for i,(domain,prior) in enumerate(zip(domains,long))
                                 if not set(domain)&set(prior))
            if any(existing<=transverse for existing in frontier):continue
            frontier={existing for existing in frontier if not transverse<existing}
            frontier.add(transverse)
    configurations=[]
    for transverse in sorted(frontier,key=lambda ids:tuple(sorted(ids))):
        domains=tuple(tuple(a for a in (0,1) if a not in prior) if i in transverse else prior
                      for i,prior in enumerate(long))
        remaining=max_work-work
        if remaining<=0:return CapPool((),False,work,'gable preference work budget exhausted')
        pool=gable_configurations(layout,available,conflicts,axes=domains,max_work=remaining)
        work+=pool.work
        if not pool.complete:return CapPool((),False,work,pool.reason)
        configurations.extend(pool.configurations)
    return CapPool(tuple(configurations),True,work)
