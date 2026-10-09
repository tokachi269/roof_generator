# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import math
from enum import Enum

from .constants import DET_EPSILON, DISTANCE_EPSILON, TIGHT_COLLINEARITY_EPSILON_DEGS


class Vector2:
    """2D vector/point class."""

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def __getitem__(self, index):
        return (self.x, self.y)[index]

    def __repr__(self):
        return f"Vector2({self.x:.03f}, {self.y:.03f})"

    @property
    def coords(self):
        return (self.x, self.y)

    def __add__(self, other: Vector2) -> Vector2:
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vector2) -> Vector2:
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Vector2:
        return Vector2(self.x * scalar, self.y * scalar)

    def __truediv__(self, scalar: float | int) -> Vector2:
        return Vector2(self.x / scalar, self.y / scalar)

    def __floordiv__(self, scalar: float | int) -> Vector2:
        return Vector2(self.x // scalar, self.y // scalar)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector2):
            return NotImplemented
        return abs(self.x - other.x) < DISTANCE_EPSILON and abs(self.y - other.y) < DISTANCE_EPSILON

    def __neg__(self) -> Vector2:
        return Vector2(-self.x, -self.y)

    def dot(self, other: Vector2) -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: Vector2) -> float:
        return self.x * other.y - self.y * other.x

    def length(self) -> float:
        return (self.x**2 + self.y**2) ** 0.5

    def normalized(self) -> Vector2:
        """Returns a copy of this vector, normalized by its length. It does not normalize itself."""
        return self / self.length()


class Orientation(Enum):
    """Orientation of a vector with respect to another vector. Note that here we treat vectors as direction vectors. The
    same orientation may not hold if the vectors are translated to their respective origins, for example when comparing
    rays.

        Note: It is encouraged to use methods for comparisons instead of directly using == or != operators.
    """

    _LEFT = 0
    _RIGHT = 1
    _ALIGNED = 2
    _OPPOSITE = 3

    def is_left_exclusive(self) -> bool:
        """The orientation signifies left, but does not include collinear cases."""
        return self == self._LEFT

    def is_left_inclusive(self, allow_aligned: bool = True, allow_opposite: bool = True) -> bool:
        """The orientation signifies left, and includes collinear cases if allowed."""
        if self == self._LEFT:
            return True
        if self == self._ALIGNED:
            return allow_aligned
        if self == self._OPPOSITE:
            return allow_opposite
        return False

    def is_right_exclusive(self) -> bool:
        """The orientation signifies right, but does not include collinear cases."""
        return self == self._RIGHT

    def is_right_inclusive(self, allow_aligned: bool = True, allow_opposite: bool = True) -> bool:
        """The orientation signifies right, and includes collinear cases if allowed."""
        if self == self._RIGHT:
            return True
        if self == self._ALIGNED:
            return allow_aligned
        if self == self._OPPOSITE:
            return allow_opposite
        return False

    def is_aligned(self) -> bool:
        """The vectors are aligned, i.e. they are parallel and point in the same direction."""
        return self == self._ALIGNED

    def is_opposite(self) -> bool:
        """The vectors are opposite, i.e. they are (anti)-parallel pointing in opposite directions."""
        return self == self._OPPOSITE

    def is_collinear(self) -> bool:
        """The vectors are collinear, i.e. they are parallel/aligned or anti-parallel/opposite."""
        return self == self._ALIGNED or self == self._OPPOSITE

    @classmethod
    def of_vec_with_respect_to(
        cls,
        vec: Vector2,
        wrt: Vector2,
        *,
        collinearity_epsilon_degrees: float = TIGHT_COLLINEARITY_EPSILON_DEGS,
    ):
        """Computes and returns the orientation of `vec` with respect to `wrt`. Both vectors are normalized before
        computing the orientation, to guarantee that the result is consistent.

        Args:
            vec: Vector to compute orientation of.
            wrt: Vector to compute orientation with respect to.
            collinearity_epsilon_degrees: Epsilon value in degrees to consider vectors collinear. If the angle between
                the vectors is less than this value, they are considered collinear.

        Returns:
            _description_
        """
        vec = vec.normalized()
        wrt = wrt.normalized()

        dot = wrt.dot(vec)
        cross = wrt.cross(vec)
        angle_radians = math.atan2(cross, dot)
        angle_degrees = math.degrees(angle_radians)
        if abs(angle_degrees) < collinearity_epsilon_degrees:
            return cls._ALIGNED
        if abs(180 - abs(angle_degrees)) < collinearity_epsilon_degrees:
            return cls._OPPOSITE
        if angle_degrees > 0:
            return cls._LEFT
        return cls._RIGHT


class Ray2:
    """2D ray class, defined by an origin and a direction vector."""

    def __init__(self, origin: Vector2, direction: Vector2):
        """Initialize the ray, automatically normalizing the direction vector."""
        self.origin = origin
        self.direction = direction.normalized()

    def intersection_with_ray(
        self,
        other: Ray2,
        *,
        allow_forward_collinear: bool = True,
        allow_backward_collinear: bool = True,
        dist_epsilon: float = DISTANCE_EPSILON,
        collinearity_epsilon_deg: float = TIGHT_COLLINEARITY_EPSILON_DEGS,
    ) -> Vector2 | None:
        """Compute intersection point of this ray with another ray.

        Args:
            other: Ray to compute intersection with.
            allow_forward_collinear: Whether to allow finding an intersection point when the rays are facing the same
                direction, and the other ray's origin is ahead of this ray's origin. This is useful for bisectors to
                find intersections with other bisectors that share direction but whose vertex is ahead of ours.
            allow_backward_collinear: Whether to allow finding an intersection point when the rays are facing the same
                direction, and this ray's origin is ahead of the other ray's origin. This is useful for bisectors to
                find that their vertex is ahead and intersected by the other bisector.
            dist_epsilon: Epsilon to compare distances.
            collinearity_epsilon_deg: Epsilon in degrees to consider vectors collinear. If the angle between the vectors
                is less than this value, they are considered collinear.

        Raises:
            RuntimeError: If computations take unexpected values (this would signal an implementation error).

        Returns:
            The intersection point if it exists, according to the args, or None if the rays do not intersect.
        """
        # General case, compute the intersection point.
        # Calculate the determinant.
        det = self.direction.cross(other.direction)
        if abs(det) > DET_EPSILON:
            # Calculate the difference between origins.
            diff = other.origin - self.origin

            # Calculate parameters t and u.
            t = diff.cross(other.direction) / det
            u = diff.cross(self.direction) / det

            # Check if intersection point is on both rays.
            if t >= -dist_epsilon and u >= -dist_epsilon:
                # Calculate and return the intersection point
                return self.origin + self.direction * t
            else:
                # The intx
                return None

        # The code below handles the case when the rays are fairly collinear, but not precisely. In that case,
        # we detect approximate collinear intersections, if allowed by the caller.

        # If not allowed, we did not find a collision so far.
        if not allow_backward_collinear and not allow_forward_collinear:
            return None
        # If the origins are the same, then we also don't want to collide with ourselves.
        if self.origin == other.origin:
            return None

        # If allowed, check still the orientation (this could be optimized since we already have the det).
        ori = Orientation.of_vec_with_respect_to(
            vec=other.direction, wrt=self.direction, collinearity_epsilon_degrees=collinearity_epsilon_deg
        )
        if ori.is_aligned():
            # Compute whether the other ray is ahead/forward or behind/backward with respect to us.
            cos_epsilon = math.cos(math.radians(collinearity_epsilon_deg))
            self_to_other_dir = (other.origin - self.origin).normalized()
            self_to_other_cos = self_to_other_dir.dot(self.direction)
            has_foward_collinear = self_to_other_cos >= cos_epsilon
            has_backward_collinear = self_to_other_cos <= -cos_epsilon
            if allow_forward_collinear and has_foward_collinear:
                return other.origin
            if allow_backward_collinear and has_backward_collinear:
                return self.origin
            # No collinear intersection allowed or found.
            return None
        elif ori.is_opposite():
            # Anti-parallel rays do not intersect (arguable claim, but for our purposes they don't).
            return None

        # No intersection found, not collinear trick.
        return None


class Line2:
    """2D line class, defined by a point and a direction vector. Unlike a Ray, Lines are infinite and undirected."""

    def __init__(self, point: Vector2, direction: Vector2):
        self.point = point
        self.direction = direction.normalized()

    def intersection_with_ray(
        self, ray: Ray2, *, collinearity_epsilon_deg: float = TIGHT_COLLINEARITY_EPSILON_DEGS
    ) -> Vector2 | None:
        """Compute intersection point of this line with a ray.

        Args:
            ray: Ray to compute intersection with.
            collinearity_epsilon_deg: TBD

        Returns:
            The intersection point if it exists, or None if the line and ray do not intersect.
        """
        collinearity_sin_epsilon = math.sin(math.radians(collinearity_epsilon_deg))

        # Get determinant and check for parallelism.
        det = self.direction.cross(ray.direction)
        if abs(det) <= collinearity_sin_epsilon:
            return None

        # Compute the intersection point.
        diff = ray.origin - self.point
        u = diff.cross(self.direction) / det

        # Check if intersection point is on the ray.
        if u >= 0:
            ret = ray.origin + ray.direction * u
            assert ret == self.point + self.direction * (diff.cross(ray.direction) / det)
            return ret

        # No intersection if u < 0 (ray points away).
        return None

    def intersection_with_line(
        self, line: Line2, *, collinearity_epsilon_deg: float = TIGHT_COLLINEARITY_EPSILON_DEGS
    ) -> Vector2 | None:
        """Compute intersection point of this line with another line.

        Args:
            line: Line to compute intersection with.
            collinearity_epsilon_deg: TBD

        Returns:
            The intersection point if it exists, or None if the lines do not intersect.
        """
        collinearity_sin_epsilon = math.sin(math.radians(collinearity_epsilon_deg))

        # Get determinant and check for parallelism.
        det = self.direction.cross(line.direction)
        if abs(det) <= collinearity_sin_epsilon:
            return None

        # Compute the intersection point.
        diff = line.point - self.point
        t = diff.cross(line.direction) / det
        intersection_point = self.point + self.direction * t
        return intersection_point

    def signed_distance(self, point: Vector2) -> float:
        """Compute the signed distance of a point to this line. The sign indicates on which side of the line the point
        lies.

        Args:
            point: Point to compute distance to.

        Returns:
            The signed distance of the point to the line.
        """
        perp_vector = Vector2(-self.direction.y, self.direction.x)
        return perp_vector.dot(point - self.point)

    def find_point_with_min_distance_along_vector(
        self,
        point: Vector2,
        vector: Vector2,
        min_distance: float,
        *,
        collinearity_epsilon_deg: float = TIGHT_COLLINEARITY_EPSILON_DEGS,
    ) -> tuple[float, Vector2]:
        """Find a point along the given vector that is at a minimum distance from this line. In order to travel the
        vector we start at the given `point`, which is expected to be on the line.

        Args:
            point: Point to start from. Expected to be on the line.
            vector: Vector to travel along.
            min_distance: Minimum distance that the new point should have with respect to the line. For clarity,
                this is not the same as the distance traveled along the vector.
            collinearity_epsilon_deg: Collinearity epsilon in degrees, to make sure the vector and the line
                are not collinear. If their angle is less than this value, a ValueError is raised.

        Raises:
            ValueError: If the vector and the line are collinear, according to the given epsilon.

        Returns:
            A tuple with the distance traveled along the vector, and the new point at that distance.
        """
        vector = vector.normalized()

        # Make sure they are not parallel, to prevent div/0.
        ori = Orientation.of_vec_with_respect_to(
            vec=vector, wrt=self.direction, collinearity_epsilon_degrees=collinearity_epsilon_deg
        )
        if ori.is_collinear():
            raise ValueError("The vector and the line direction are parallel; cannot achieve MIN_D.")

        # Calculate sin(theta) using the cross product
        sin_theta_abs = abs(self.direction.cross(vector))

        # Calculate the distance to move along the vector, and return the new point at that distance.
        desired_d = min_distance / sin_theta_abs
        p_along_vec = point + vector * desired_d
        return desired_d, p_along_vec
