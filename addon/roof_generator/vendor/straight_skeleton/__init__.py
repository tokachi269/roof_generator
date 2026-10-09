# SPDX-License-Identifier: BSD-3-Clause
__version__ = '0.1.0'

from .algorithm import PointList, StraightSkeletonAlgorithm
from .skeleton import Skeleton


def compute_skeleton(exterior: PointList, holes: list[PointList]) -> Skeleton:
    """Computes the straight skeleton of the polygon defined by the given exterior outline and interior holes.

    Args:
        exterior: List of vertices that define the exterior of the polygon. Must be provided in COUNTER-CLOCKWISE,
            with +X-right and +Y-up.
        holes: List of holes, each as a list of vertices that define the hole. Must be provided in CLOCKWISE order,
            with +X-right and +Y-up (opposite of the exterior vertices).

    Returns:
        The straight skeleton of the polygon defined by the exterior and holes.
    """
    algorithm = StraightSkeletonAlgorithm()
    return algorithm.compute_skeleton(exterior=exterior, holes=holes)
