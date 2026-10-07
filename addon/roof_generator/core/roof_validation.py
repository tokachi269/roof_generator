# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent invariants for a single projected roof disk; never edits geometry."""

from __future__ import annotations

from collections import defaultdict, Counter
from dataclasses import dataclass
import itertools
import numpy as np
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union

from .roof_geometry import UnsupportedRoofError


@dataclass(frozen=True)
class MeshValidation:
    vertices: int
    faces: int
    edges: int
    boundary_edges: int
    max_planarity_error: float
    projected_area: float
    features: dict[str, int]


def _connected(nodes, neighbors):
    nodes = set(nodes)
    if not nodes:
        return False
    visited = set()
    todo = [min(nodes)]
    while todo:
        v = todo.pop()
        if v in visited:
            continue
        visited.add(v)
        todo.extend(set(neighbors.get(v, ())) - visited)
    return visited == nodes


def validate_mesh(mesh, footprint, tolerance=1e-7) -> MeshValidation:
    def require(condition, message):
        if not condition:
            raise UnsupportedRoofError(message)

    vertices = np.asarray(mesh.vertices, dtype=float)
    require(
        vertices.ndim == 2
        and vertices.shape[1] == 3
        and len(vertices) >= 3
        and np.isfinite(vertices).all(),
        "invalid/nonfinite roof vertices",
    )
    require(np.isfinite(tolerance) and tolerance > 0, "mesh tolerance must be positive")
    faces = mesh.faces
    require(bool(faces), "roof mesh has no faces")
    buckets = defaultdict(list)
    for i, p in enumerate(vertices):
        cell = tuple(int(np.floor(x / tolerance)) for x in p[:2])
        for delta in itertools.product([-1, 0, 1], repeat=2):
            for j in buckets.get((cell[0] + delta[0], cell[1] + delta[1]), ()):
                require(
                    np.linalg.norm(vertices[j, :2] - p[:2]) > tolerance,
                    "duplicate roof projection vertex / unshared height step",
                )
        buckets[cell].append(i)
    seen = set()
    incidence = defaultdict(list)
    links = defaultdict(lambda: defaultdict(set))
    polygons = []
    errors = []
    referenced = set()
    for fi, face in enumerate(faces):
        require(
            len(face) >= 3 and len(set(face)) == len(face), "invalid roof face loop"
        )
        require(
            all(
                isinstance(i, (int, np.integer)) and 0 <= i < len(vertices)
                for i in face
            ),
            "roof face index out of bounds",
        )
        referenced.update(face)
        cycle = tuple(face)
        rev = tuple(reversed(face))
        signature = min(cycle[i:] + cycle[:i] for i in range(len(face)))
        signature = min(signature, min(rev[i:] + rev[:i] for i in range(len(face))))
        require(signature not in seen, "duplicate roof face")
        seen.add(signature)
        p = vertices[list(face)]
        centered = p - p[0]
        normal = sum(
            (
                np.cross(centered[i], centered[(i + 1) % len(face)])
                for i in range(len(face))
            ),
            start=np.zeros(3),
        )
        require(np.linalg.norm(normal) > tolerance**2, "zero-area roof face")
        require(normal[2] > 0, "inconsistent/upside-down roof face normal")
        covariance = p - np.mean(p, axis=0)
        _, _, vh = np.linalg.svd(covariance, full_matrices=True)
        error = float(max(abs(covariance @ vh[-1])))
        require(error <= tolerance, "nonplanar roof face")
        errors.append(error)
        poly = Polygon(p[:, :2])
        require(
            poly.is_valid and poly.area > tolerance**2,
            "self-crossing/zero projected area roof face",
        )
        polygons.append(poly)
        for k, v in enumerate(face):
            a, b = face[k - 1], face[(k + 1) % len(face)]
            links[v][a].add(b)
            links[v][b].add(a)
            edge = tuple(sorted((v, b)))
            incidence[edge].append((fi, v, b))
    require(referenced == set(range(len(vertices))), "unreferenced roof vertices")
    adjacency = defaultdict(set)
    boundary = defaultdict(set)
    perimeter = []
    for edge, items in incidence.items():
        require(len(items) in {1, 2}, "nonmanifold roof edge")
        a, b = edge
        if len(items) == 2:
            (f0, u0, v0), (f1, u1, v1) = items
            require(u0 == v1 and v0 == u1, "inconsistent adjacent face normals")
            adjacency[f0].add(f1)
            adjacency[f1].add(f0)
        else:
            boundary[a].add(b)
            boundary[b].add(a)
            perimeter.append(LineString(vertices[[a, b], :2]))
        vector = vertices[b, :2] - vertices[a, :2]
        length2 = np.dot(vector, vector)
        require(length2 > tolerance**2, "zero-length roof edge")
        t = (vertices[:, :2] - vertices[a, :2]) @ vector / length2
        distances = np.linalg.norm(
            (vertices[:, :2] - vertices[a, :2]) - t[:, None] * vector, axis=1
        )
        for i in np.nonzero(
            (t > tolerance / np.sqrt(length2))
            & (t < 1 - tolerance / np.sqrt(length2))
            & (distances <= tolerance)
        )[0]:
            require(i in edge, "roof T-junction (vertex inside unsplit edge)")
    require(_connected(range(len(faces)), adjacency), "disconnected roof surface")
    require(
        boundary
        and all(len(n) == 2 for n in boundary.values())
        and _connected(boundary, boundary),
        "roof has a hole or nonmanifold perimeter",
    )
    for v, link in links.items():
        require(_connected(link, link), "nonmanifold vertex fan")
        degrees = [len(n) for n in link.values()]
        if v in boundary:
            require(
                degrees.count(1) == 2 and all(d in {1, 2} for d in degrees),
                "nonmanifold boundary vertex",
            )
        else:
            require(all(d == 2 for d in degrees), "nonmanifold interior vertex")
    require(
        len(vertices) - len(incidence) + len(faces) == 1,
        "roof surface is not one topological disk",
    )
    cover = unary_union(polygons)
    area_tolerance = tolerance * footprint.length
    require(
        sum(p.area for p in polygons) - cover.area <= area_tolerance,
        "overlapping/internal roof faces",
    )
    require(
        cover.symmetric_difference(footprint).area <= area_tolerance,
        "roof projection has holes or extends outside footprint",
    )
    require(
        unary_union(perimeter).hausdorff_distance(footprint.boundary) <= tolerance * 2,
        "roof perimeter does not match footprint",
    )
    require(
        all(tuple(sorted(edge)) in incidence for edge in mesh.edge_features),
        "feature references a missing roof edge",
    )
    return MeshValidation(
        len(vertices),
        len(faces),
        len(incidence),
        len(perimeter),
        max(errors),
        float(cover.area),
        dict(Counter(mesh.edge_features.values())),
    )
