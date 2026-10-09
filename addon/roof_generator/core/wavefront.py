# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded incidence source for polygon roof topology, never an embedding solver."""
from dataclasses import dataclass
from threading import Lock

from .errors import UnsupportedRoofError, GenerationIssue
from ..vendor.straight_skeleton import compute_skeleton
from ..vendor.straight_skeleton import algorithm


@dataclass(frozen=True)
class Wavefront:
    points: tuple[tuple[float, float], ...]
    faces: tuple[tuple[int, ...], ...]
    work: int


class WavefrontBudget(UnsupportedRoofError):
    """An unfinished incidence search must never supply a selectable prefix."""


class Events(algorithm.NoopAlgorithmTracer):
    def __init__(self, limit):
        self.limit = limit
        self.work = 0

    def on_step_begin(self, step, time, algorithm):
        self.work += 1
        if self.work > self.limit:
            raise WavefrontBudget('roof wavefront work budget exhausted',
                                  issues=(GenerationIssue('topology','wavefront_incomplete'),))


# The bundled library resets module-wide event/vertex IDs and a tracer. Copy
# the complete incidence under this lock. Subsequent graph construction and
# fixed embedding operate on independent immutable records.
_lock = Lock()


def wavefront(fp, *, max_work=65536):
    if not fp.orthogonal:
        raise UnsupportedRoofError('polygon wavefront requires orthogonal input')
    if max_work < 1:
        raise ValueError('positive wavefront work budget required')
    trace = Events(max_work)
    with _lock:
        previous = algorithm.GLOBAL_ALGORITHM_TRACER
        algorithm.set_global_algorithm_tracer(trace)
        try:
            # The input is already in the core's intrinsic perimeter frame.
            # Reintroducing raw units made event handling depend on a uniform
            # building scale (including the existing symmetric Cross). Keep
            # this one coordinate convention for every input; no retry or
            # perturbation of a failed event.
            source = compute_skeleton(list(fp.vertices), [])
            points = tuple((node.position.x,node.position.y) for node in source.nodes)
            faces = tuple(tuple(face[:-1]) for face in source.get_faces())
            return Wavefront(points, faces, trace.work)
        except WavefrontBudget:
            raise
        except Exception as exc:
            raise UnsupportedRoofError('unresolved polygon roof event: '+str(exc),
                                       issues=(GenerationIssue('topology','wavefront_event'),)) from exc
        finally:
            algorithm.set_global_algorithm_tracer(previous)
