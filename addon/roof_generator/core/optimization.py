# SPDX-License-Identifier: GPL-3.0-or-later
"""Ren et al. covariance energy on fixed incidence; stdlib numerical solve."""

from dataclasses import dataclass
import math
from .errors import UnsupportedRoofError


@dataclass(frozen=True)
class Embedding:
    vertices: tuple[tuple[float, float, float], ...]
    iterations: int
    energy: float
    planarity_error: float
    direction_error: float
    slope_error: float


def covariance_plane(points):
    """Smallest covariance eigenpair by symmetric 3x3 Jacobi rotations."""
    mean = tuple(sum(p[k] for p in points) / len(points) for k in range(3))
    centered = [tuple(p[k] - mean[k] for k in range(3)) for p in points]
    a = [
        [sum(p[j] * p[k] for p in centered) / (len(points) - 1) for k in range(3)]
        for j in range(3)
    ]
    v = [[float(j == k) for k in range(3)] for j in range(3)]
    for _ in range(32):
        p, q = max(((0, 1), (0, 2), (1, 2)), key=lambda pair: abs(a[pair[0]][pair[1]]))
        if abs(a[p][q]) <= 1e-18:
            break
        angle = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
        c, s = math.cos(angle), math.sin(angle)
        ap, aq, off = a[p][p], a[q][q], a[p][q]
        a[p][p] = c * c * ap - 2 * c * s * off + s * s * aq
        a[q][q] = s * s * ap + 2 * c * s * off + c * c * aq
        a[p][q] = a[q][p] = 0.0
        for k in range(3):
            if k not in (p, q):
                x, y = a[k][p], a[k][q]
                a[k][p] = a[p][k] = c * x - s * y
                a[k][q] = a[q][k] = s * x + c * y
            x, y = v[k][p], v[k][q]
            v[k][p], v[k][q] = c * x - s * y, s * x + c * y
    smallest = min(range(3), key=lambda k: a[k][k])
    normal = tuple(v[k][smallest] for k in range(3))
    if normal[2] < 0:
        normal = tuple(-x for x in normal)
    residual = tuple(sum(n * p[k] for k, n in enumerate(normal)) for p in centered)
    return normal, residual


def _linear_solve(matrix, rhs):
    """Dense partial-pivot elimination for these small damped normal systems."""
    n = len(rhs)
    a = [list(row) + [value] for row, value in zip(matrix, rhs)]
    for k in range(n):
        pivot = max(range(k, n), key=lambda i: abs(a[i][k]))
        if abs(a[pivot][k]) < 1e-24:
            raise UnsupportedRoofError("singular nonlinear solve system")
        a[k], a[pivot] = a[pivot], a[k]
        for i in range(k + 1, n):
            ratio = a[i][k] / a[k][k]
            for j in range(k + 1, n + 1):
                a[i][j] -= ratio * a[k][j]
    result = [0.0] * n
    for i in reversed(range(n)):
        result[i] = (a[i][n] - sum(a[i][j] * result[j] for j in range(i + 1, n))) / a[
            i
        ][i]
    return result


def _parameters(problem):
    """Eliminate hard linear ridge constraints from the free XY/Z variables."""
    coordinates = tuple((i, k) for i in problem.variable_xy for k in (0, 1)) + tuple(
        (i, 2) for i in problem.variable_z
    )
    ids = {value: i for i, value in enumerate(coordinates)}
    rows = []
    for (a, b), direction in problem.ridge_directions:
        row = [0.0] * (len(coordinates) + 1)
        for vertex, sign in ((b, 1), (a, -1)):
            for k, coefficient in ((0, sign * direction[1]), (1, -sign * direction[0])):
                if (vertex, k) in ids:
                    row[ids[vertex, k]] += coefficient
                else:
                    row[-1] -= coefficient * problem.initial_vertices[vertex][k]
        rows.append(row)
    pivots = []
    rank = 0
    for col in range(len(coordinates)):
        if rank == len(rows):
            break
        pivot = max(range(rank, len(rows)), key=lambda i: abs(rows[i][col]))
        if abs(rows[pivot][col]) < 1e-12:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        value = rows[rank][col]
        rows[rank] = [v / value for v in rows[rank]]
        for i in range(len(rows)):
            if i != rank:
                value = rows[i][col]
                rows[i] = [a - value * b for a, b in zip(rows[i], rows[rank])]
        pivots.append(col)
        rank += 1
    if any(
        max((abs(v) for v in r[:-1]), default=0) < 1e-12 and abs(r[-1]) > 1e-10
        for r in rows[rank:]
    ):
        raise UnsupportedRoofError("fixed ridge direction constraints conflict")
    free = tuple(i for i in range(len(coordinates)) if i not in pivots)

    def unpack(values):
        flat = [0.0] * len(coordinates)
        for i, value in zip(free, values):
            flat[i] = value
        for pivot, row in zip(pivots, rows):
            flat[pivot] = row[-1] - sum(row[j] * flat[j] for j in free)
        points = [list(p) for p in problem.initial_vertices]
        for i, z in problem.fixed_z:
            points[i][2] = z
        for (i, k), value in zip(coordinates, flat):
            points[i][k] = value
        return tuple(tuple(p) for p in points)

    return [
        problem.initial_vertices[coordinates[i][0]][coordinates[i][1]] for i in free
    ], unpack


def optimize(problem, *, tolerance=4e-9, max_iterations=240):
    """Fixed-variable nonlinear least squares of covariance planarity residuals.

    Positive regularization is explicitly continued to zero to meet a hard
    mesh planarity tolerance. A failure emits no approximate mesh.
    """
    values, unpack = _parameters(problem)
    iterations = 0

    def residuals(values, weight):
        vertices = unpack(values)
        result = []
        normals = []
        for face in problem.faces:
            normal, residual = covariance_plane([vertices[i] for i in face])
            normals.append(normal)
            result.extend(r / math.sqrt(len(face) - 1) for r in residual)
        # A planar face with its declared eave and pitch satisfies this
        # point-to-plane constraint. Unlike fitting a normal to a temporarily
        # nonplanar iterate, its derivative stays continuous. The covariance
        # residual above remains the paper's roof planarity objective.
        result.extend(
            (
                vertices[i][2]
                - origin[2]
                - pitch * sum((vertices[i][k] - origin[k]) * inward[k] for k in (0, 1))
            )
            / math.sqrt(1 + pitch * pitch)
            for fi, origin, inward, pitch in problem.slope_constraints
            for i in problem.faces[fi]
        )
        if weight:
            result.extend(
                math.sqrt(weight) * (vertices[i][k] - problem.initial_vertices[i][k])
                for i in problem.variable_xy
                for k in (0, 1)
            )
        return result

    for weight in (1e-4, 1e-8, 0.0):
        damping = 1e-5
        for _ in range(max_iterations // 3):
            iterations += 1
            r = residuals(values, weight)
            energy = sum(x * x for x in r)
            if not math.isfinite(energy):
                raise UnsupportedRoofError("nonfinite nonlinear objective")
            if not values:
                break
            columns = []
            step = 1e-6
            for k in range(len(values)):
                upper = list(values)
                lower = list(values)
                upper[k] += step
                lower[k] -= step
                columns.append(
                    [
                        (a - b) / (2 * step)
                        for a, b in zip(
                            residuals(upper, weight), residuals(lower, weight)
                        )
                    ]
                )
            gradient = [sum(a * b for a, b in zip(column, r)) for column in columns]
            normal = [
                [sum(a * b for a, b in zip(left, right)) for right in columns]
                for left in columns
            ]
            for k in range(len(values)):
                normal[k][k] += damping
            delta = _linear_solve(normal, [-v for v in gradient])
            trial = [a + b for a, b in zip(values, delta)]
            objective = sum(v * v for v in residuals(trial, weight))
            if objective < energy:
                values = trial
                damping = max(1e-12, damping / 3)
                if max(abs(v) for v in delta) < 1e-12:
                    break
            else:
                damping *= 10
                if damping > 1e12:
                    break
            if (
                weight == 0
                and max(abs(v) for v in residuals(values, 0)) < tolerance / 4
            ):
                break
    vertices = unpack(values)
    residual = [
        r for f in problem.faces for r in covariance_plane([vertices[i] for i in f])[1]
    ]
    error = max((abs(r) for r in residual), default=0)
    direction_error = max(
        (
            abs(
                (vertices[b][0] - vertices[a][0]) * d[1]
                - (vertices[b][1] - vertices[a][1]) * d[0]
            )
            for (a, b), d in problem.ridge_directions
        ),
        default=0,
    )
    slope_error = max(
        (
            abs(
                vertices[i][2]
                - origin[2]
                - pitch * sum((vertices[i][k] - origin[k]) * inward[k] for k in (0, 1))
            )
            / math.sqrt(1 + pitch * pitch)
            for fi, origin, inward, pitch in problem.slope_constraints
            for i in problem.faces[fi]
        ),
        default=0,
    )
    if error > tolerance or direction_error > tolerance or slope_error > tolerance:
        raise UnsupportedRoofError(
            f"nonlinear solve did not converge: planarity={error:.3g}, ridge={direction_error:.3g}, slope={slope_error:.3g}, iterations={iterations}"
        )
    return Embedding(
        vertices,
        iterations,
        sum(v * v for v in residuals(values, 0)),
        error,
        direction_error,
        slope_error,
    )
