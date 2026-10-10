# SPDX-License-Identifier: GPL-3.0-or-later
"""Necessary feasibility of explicit GeometryProblem planes; no roof decisions."""
from .errors import UnsupportedRoofError


def plane_equations(problem):
    """Declared face, XYZ coefficients and RHS; no fitted or inferred plane."""
    return tuple(
        (face, (-pitch * inward[0], -pitch * inward[1], 1.0),
         origin[2] - pitch * sum(origin[k] * inward[k] for k in (0, 1)))
        for face, origin, inward, pitch in problem.slope_constraints
    )


def has_fixed_planes(problem):
    return {face for face, *_ in problem.slope_constraints} == set(range(len(problem.faces)))


def check_planes(problem, tolerance=1e-8):
    """Reject inconsistent linear slope/anchor equations before optimization.

    Each vertex must satisfy all its incident declared source planes. Checking
    their augmented rank is necessary, not sufficient, for a mesh embedding.
    No coordinate, face, edge kind, constraint or topology is changed here.
    """
    equations=[[] for _ in problem.initial_vertices]
    for face, coefficients, rhs in plane_equations(problem):
        row=[*coefficients,rhs]
        for vertex in problem.faces[face]:equations[vertex].append(row[:])
    fixed=dict(problem.fixed_z)
    for vertex,point in enumerate(problem.initial_vertices):
        rows=equations[vertex]
        if vertex not in problem.variable_xy:
            rows.extend(([1.,0.,0.,point[0]],[0.,1.,0.,point[1]]))
        if vertex in fixed:rows.append([0.,0.,1.,fixed[vertex]])
        pivot=0
        for column in range(3):
            if pivot==len(rows):break
            index=max(range(pivot,len(rows)),key=lambda i:abs(rows[i][column]))
            if abs(rows[index][column])<1e-12:continue
            rows[pivot],rows[index]=rows[index],rows[pivot]
            scale=rows[pivot][column]
            rows[pivot]=[v/scale for v in rows[pivot]]
            for i in range(len(rows)):
                if i==pivot:continue
                factor=rows[i][column]
                rows[i]=[a-factor*b for a,b in zip(rows[i],rows[pivot])]
            pivot+=1
        if any(max(abs(v) for v in row[:3])<1e-10 and abs(row[3])>tolerance for row in rows):
            raise UnsupportedRoofError('explicit slope and anchor equations are inconsistent at vertex '+str(vertex))
