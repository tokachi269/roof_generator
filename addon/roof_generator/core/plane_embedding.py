# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed-plane embedding with hard anchors and minimum XY displacement."""

import math
from .constraints import has_fixed_planes, plane_equations
from .errors import UnsupportedRoofError


def _reduce(rows, width, tolerance):
    """Normalized partial-pivot RREF; return independent equations and pivots."""
    rows = [list(row) for row in rows]
    for row in rows:
        scale = math.sqrt(sum(x * x for x in row[:width]))
        if scale:
            row[:] = [x / scale for x in row]
    pivots = []
    for column in range(width):
        rank = len(pivots)
        if rank == len(rows):
            break
        pivot = max(range(rank, len(rows)), key=lambda i: abs(rows[i][column]))
        if abs(rows[pivot][column]) <= 1e-12:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        factor = rows[rank][column]
        rows[rank] = [x / factor for x in rows[rank]]
        for i, row in enumerate(rows):
            if i != rank:
                factor = row[column]
                if factor:
                    rows[i] = [a - factor * b for a, b in zip(row, rows[rank])]
        pivots.append(column)
    if any(abs(row[-1]) > tolerance for row in rows[len(pivots):]):
        raise UnsupportedRoofError("fixed plane, anchor or ridge equations conflict")
    return rows[:len(pivots)], pivots


def embed_planes(problem, *, tolerance=4e-9):
    """Solve fully declared planes; never infer topology or retry optimization."""
    if not has_fixed_planes(problem):
        raise UnsupportedRoofError("linear embedding requires a plane for every face")
    if {i for f in problem.faces for i in f} != set(range(len(problem.initial_vertices))):
        raise UnsupportedRoofError("fixed-plane embedding has an unconstrained vertex")
    initial = [list(p) for p in problem.initial_vertices]
    for i, z in problem.fixed_z:
        initial[i][2] = z
    # Eliminate height first: its plane coefficient is one, including tiny pitch.
    coordinates = tuple((i, 2) for i in problem.variable_z) + tuple(
        (i, k) for i in problem.variable_xy for k in (0, 1)
    )
    ids = {coordinate: j for j, coordinate in enumerate(coordinates)}
    equations = []

    def equation(terms, rhs):
        row = [0.0] * (len(coordinates) + 1)
        row[-1] = rhs
        for vertex, component, coefficient in terms:
            row[-1] -= coefficient * initial[vertex][component]
            if (vertex, component) in ids:
                row[ids[vertex, component]] += coefficient
        equations.append(row)

    planes = plane_equations(problem)
    for face, coefficients, rhs in planes:
        for vertex in problem.faces[face]:
            equation(((vertex, k, a) for k, a in enumerate(coefficients)), rhs)
    for (a, b), direction in problem.ridge_directions:
        equation(((v, k, value) for v, sign in ((b, 1), (a, -1))
                  for k, value in ((0, sign * direction[1]), (1, -sign * direction[0]))), 0.0)
    rows, pivots = _reduce(equations, len(coordinates), tolerance)
    free = [i for i in range(len(coordinates)) if i not in pivots]
    correction = [0.0] * len(coordinates)
    for column, row in zip(pivots, rows):
        correction[column] = row[-1]
    if free:
        basis = []
        for column in free:
            vector = [0.0] * len(coordinates)
            vector[column] = 1.0
            for pivot, row in zip(pivots, rows):
                vector[pivot] = -row[column]
            basis.append(vector)
        xy = [j for j, (_, k) in enumerate(coordinates) if k < 2]
        gram = [[sum(a[j] * b[j] for j in xy) for b in basis] for a in basis]
        rhs = [-sum(a[j] * correction[j] for j in xy) for a in basis]
        projection, columns = _reduce([row + [value] for row, value in zip(gram, rhs)],
                                      len(free), tolerance)
        if len(columns) != len(free):
            raise UnsupportedRoofError("fixed-plane XY displacement minimum is singular")
        values = [0.0] * len(free)
        for column, row in zip(columns, projection):
            values[column] = row[-1]
        correction = [q + sum(t * b[j] for t, b in zip(values, basis))
                      for j, q in enumerate(correction)]
    for (vertex, component), delta in zip(coordinates, correction):
        initial[vertex][component] += delta
    vertices = tuple(tuple(p) for p in initial)
    if any(not math.isfinite(x) for p in vertices for x in p):
        raise UnsupportedRoofError("nonfinite fixed-plane embedding")
    error = max((abs(sum(a * vertices[i][k] for k, a in enumerate(coefficients)) - rhs)
                 / math.sqrt(sum(a * a for a in coefficients))
                 for face, coefficients, rhs in planes for i in problem.faces[face]), default=0)
    ridge_error = max((abs((vertices[b][0] - vertices[a][0]) * d[1]
                           - (vertices[b][1] - vertices[a][1]) * d[0])
                       for (a, b), d in problem.ridge_directions), default=0)
    if error > tolerance or ridge_error > tolerance:
        raise UnsupportedRoofError("fixed-plane embedding exceeds plane or ridge tolerance")
    return vertices
