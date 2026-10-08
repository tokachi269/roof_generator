# SPDX-License-Identifier: GPL-3.0-or-later
"""Stable namespaced decisions; no process hash or sequential PRNG state."""

import hashlib
import json
import math


def derive(seed, namespace, stable_id=""):
    if isinstance(seed, bool) or not isinstance(seed, (int, str)):
        raise ValueError("generation seed must be an integer or string")
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("seed namespace must be a nonempty string")
    payload = json.dumps(
        [seed, namespace, stable_id],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.blake2b(
        payload, digest_size=16, person=b"roof-generator"
    ).hexdigest()


def choose(items, seed, namespace, *, key):
    items = tuple(items)
    if not items:
        raise ValueError("seed selection requires valid candidates")
    identities = [key(item) for item in items]
    if len(set(identities)) != len(identities):
        raise ValueError("candidate stable IDs must be unique")
    return min(items, key=lambda item: (derive(seed, namespace, key(item)), key(item)))


def point_identity(fp, reference_direction=(1.0, 0.0)):
    """Geometry IDs in a declared frame, independent of indices/cyclic start.

    The orientation reference is input: rotate it with a symmetric footprint.
    Positions are relative to the bounding center in this frame, in perimeter
    units. Original edge numbers and redundant collinear vertices are excluded.
    """
    try:
        direction = tuple(float(x) for x in reference_direction)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "reference direction must be a finite nonzero XY vector"
        ) from exc
    if len(direction) != 2 or not all(math.isfinite(x) for x in direction):
        raise ValueError("reference direction must be a finite nonzero XY vector")
    size = math.hypot(*direction)
    if size <= 0:
        raise ValueError("reference direction must be a finite nonzero XY vector")
    u = tuple(x / size for x in direction)
    v = (-u[1], u[0])
    origin = fp.frame.origin

    def project(p):
        world = fp.frame.world_xy(p)
        q = tuple((world[k] - origin[k]) / fp.frame.scale for k in (0, 1))
        return tuple(sum(a * b for a, b in zip(q, axis)) for axis in (u, v))

    outline = tuple(project(p) for p in fp.vertices)
    center = tuple(
        (min(p[k] for p in outline) + max(p[k] for p in outline)) / 2 for k in (0, 1)
    )

    def identity(p):
        return tuple(round(x - c, 10) + 0.0 for x, c in zip(project(p), center))

    return identity
