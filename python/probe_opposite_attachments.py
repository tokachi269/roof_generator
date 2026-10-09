# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent metric witness for existing opposite-eave mixed incidence.

Bypasses the conservative plan predicate for a diagnostic only. It does not
change production acceptance, generate proposal ownership, or select a roof.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addon'))
from roof_generator.core.footprint import analyze
from roof_generator.core.roof_regions import propose_regions
from roof_generator.core.region_architecture import interpret_regions
from roof_generator.core.architecture import resolve
from roof_generator.core.roof_ends import roof_configurations
from roof_generator.core.topology import member_templates, _terminals
from roof_generator.core.junctions import attachments
from roof_generator.core.solve import problem, solve


def witness():
    fp=analyze(((2,0),(8,0),(8,3),(7,3),(7,6),(8,6),(8,8),(2,8),(2,6),(1,6),(1,3),(2,3)))
    regions=(((1,3),(2,3),(2,6),(1,6)),((2,0),(7,0),(7,8),(2,8)),
             ((7,0),(8,0),(8,3),(7,3)),((7,6),(8,6),(8,8),(7,8)))
    candidate=propose_regions(fp,regions,source='explicit-opposite-eave')
    authority=resolve(interpret_regions(candidate),(0,1,0,0))
    ends=next(e for e in roof_configurations(authority)
              if tuple(j.kind for j in e.joints)==('extension','shared','shared'))
    resolved=authority.with_ends(ends)
    templates=member_templates(resolved)
    ports=attachments(resolved,templates)
    c=_terminals(resolved.layout,templates,ports)
    mesh=solve(c.graph,problem(c.graph,.5,0))
    print('EXISTING_OPPOSITE_EAVE_INCIDENCE_EMBEDS',len(mesh.vertices),len(mesh.faces))
    for point in mesh.vertices:print(fp.frame.world_xyz(point))
    return resolved,c,mesh


if __name__=='__main__':witness()
