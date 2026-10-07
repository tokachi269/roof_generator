# SPDX-License-Identifier: GPL-3.0-or-later
"""Tessellate already-decided planar topology and share all edge vertices."""

from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
import itertools
import numpy as np
import shapely
from shapely.geometry import LineString
from shapely.ops import unary_union

from .roof_geometry import (
    EPS,
    UnsupportedRoofError,
    clean_ring,
    polygon_pieces,
    precise,
    ring_key,
)


from .roof_features import classify_crease


@dataclass(frozen=True)
class RoofMesh:
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, ...], ...]
    face_parts: tuple[tuple[int, ...], ...]
    # Features contain only geometric creases/perimeter, never tessellation cuts.
    edge_features: dict[tuple[int, int], str]


WELD = EPS * 4


def tessellate(topology) -> RoofMesh:
    surfaces = []
    for region in topology.regions:
        if region.polygon.interiors:
            # Holes belong to the topology; constrained triangulation is solely
            # a mesh export choice. Unconstrained Delaunay would bridge holes.
            polygons = polygon_pieces(
                shapely.constrained_delaunay_triangles(region.polygon)
            )
        else:
            polygons = (region.polygon,)
        for poly in sorted(polygons, key=ring_key):
            surfaces.append((clean_ring(poly.exterior.coords, eps=WELD), region))
    if not surfaces:
        raise UnsupportedRoofError("roof topology contains no exposed surface")
    # GEOS nodes all boundary crossings. Then weld only at tolerance and insert
    # these shared points on every incident edge, including T-junctions from
    # independent polygon clipping or constrained triangle export.
    boundary = unary_union(
        [precise(LineString(list(ring) + [ring[0]])) for ring, _ in surfaces]
    )
    points = np.asarray(shapely.get_coordinates(boundary))
    points = np.vstack([points, np.asarray([p for ring, _ in surfaces for p in ring])])
    points = sorted(set(map(tuple, points)))
    unique = []
    buckets = defaultdict(list)
    for point in points:
        cell = tuple(int(np.floor(x / WELD)) for x in point)
        near = [
            i
            for delta in itertools.product([-1, 0, 1], repeat=2)
            for i in buckets.get((cell[0] + delta[0], cell[1] + delta[1]), ())
            if np.linalg.norm(np.asarray(unique[i]) - point) <= WELD
        ]
        if not near:
            buckets[cell].append(len(unique))
            unique.append(point)
    xy = np.asarray(unique)
    faces, regions = [], []
    for ring, region in surfaces:
        face = []
        for a, b in zip(ring, ring[1:] + ring[:1]):
            a, b = np.asarray(a), np.asarray(b)
            vector = b - a
            length2 = np.dot(vector, vector)
            if length2 <= EPS**2:
                raise UnsupportedRoofError(
                    "roof region has a tolerance-degenerate edge"
                )
            t = (xy - a) @ vector / length2
            distances = np.linalg.norm((xy - a) - t[:, None] * vector, axis=1)
            ids = np.nonzero(
                (distances <= WELD)
                & (t >= -WELD / np.sqrt(length2))
                & (t < 1 - WELD / np.sqrt(length2))
            )[0]
            ids = sorted(ids, key=lambda i: (t[i], i))
            for i in ids:
                if not face or face[-1] != i:
                    face.append(int(i))
        if len(face) > 1 and face[0] == face[-1]:
            face.pop()
        if len(face) < 3 or len(set(face)) != len(face):
            raise UnsupportedRoofError(
                "roof region collapses during numerical vertex sharing"
            )
        start = min(range(len(face)), key=lambda i: face[i])
        faces.append(tuple(face[start:] + face[:start]))
        regions.append(region)
    # Remove numerical waypoints on straight edges only when every incident
    # face uses the same two neighbors. A ridge endpoint / junction has higher
    # valence and is never removed by this operation.
    neighbors = defaultdict(set)
    for face in faces:
        for a, b in zip(face, face[1:] + face[:1]):
            neighbors[a].add(b)
            neighbors[b].add(a)
    removable = set()
    for i, adjacent in neighbors.items():
        if len(adjacent) != 2:
            continue
        a, b = sorted(adjacent)
        vector = xy[b] - xy[a]
        length2 = np.dot(vector, vector)
        if length2 <= WELD**2:
            continue
        t = float(np.dot(xy[i] - xy[a], vector) / length2)
        if 0 < t < 1 and np.linalg.norm(xy[i] - xy[a] - t * vector) <= WELD:
            removable.add(i)
    faces = [tuple(i for i in face if i not in removable) for face in faces]
    if any(len(face) < 3 for face in faces):
        raise UnsupportedRoofError("roof face collapses below numerical tolerance")
    heights = defaultdict(list)
    for face, region in zip(faces, regions):
        for i in face:
            heights[i].append(region.plane.height(xy[i]))
    used = sorted(heights)
    mapping = {old: new for new, old in enumerate(used)}
    vertices = []
    for i in used:
        h = heights[i]
        if max(h) - min(h) > EPS * 20:
            raise UnsupportedRoofError(
                "unequal roof plane heights at a shared intersection vertex"
            )
        # The chosen point lies on the first incident plane; other incident
        # planes must agree within numerical tolerance, checked again below.
        vertices.append((float(xy[i, 0]), float(xy[i, 1]), float(h[0])))
    faces = [tuple(mapping[i] for i in face) for face in faces]
    order = sorted(range(len(faces)), key=lambda i: faces[i])
    faces = tuple(faces[i] for i in order)
    regions = [regions[i] for i in order]
    incidence = defaultdict(list)
    for i, face in enumerate(faces):
        for a, b in zip(face, face[1:] + face[:1]):
            incidence[tuple(sorted((a, b)))].append((i, a, b))
    features = {}
    for edge, adjacent in sorted(incidence.items()):
        if len(adjacent) == 1:
            h0, h1 = vertices[edge[0]][2], vertices[edge[1]][2]
            features[edge] = "eave" if abs(h0 - h1) <= EPS else "gable_end"
        elif len(adjacent) == 2:
            (i, a, b), (j, _, _) = adjacent
            kind = classify_crease(
                regions[i].plane,
                regions[j].plane,
                (vertices[a][:2], vertices[b][:2]),
                topology.parts,
            )
            if kind is not None:
                features[edge] = kind
        else:
            raise UnsupportedRoofError("more than two faces meet on a roof edge")
    return RoofMesh(
        tuple(vertices), faces, tuple(region.part_ids for region in regions), features
    )
