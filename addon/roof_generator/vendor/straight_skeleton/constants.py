# SPDX-License-Identifier: BSD-3-Clause
"""Module with constant definitions to share across code."""

# Note: It may be slightly dangerous to not specify units, since epsilons may need scaling depending on polygon units.
# DISTANCE_EPSILON: Epsilon to compare positions, distances, etc.
DISTANCE_EPSILON = 1e-5

# TIME_EPSILON: Used to compare event times that may have floating-point imprecision (for example to identify
# simultaneous events). Note that in skeleton computation time is equivalent to distance, and, in general, given
# the current implementation, it should probably be <= DISTANCE_EPSILON.
TIME_EPSILON = DISTANCE_EPSILON

# I have empirically seen `v.dot(v)` to fail collinearity checks if the epsilon is <=0.2
# >>> math.degrees(math.acos(1 - 1e-5))
# 0.25623472915884415
# TIGHT_COLLINEARITY_EPSILON_DEGS: Used when we want to check that vectors are almost collinear.
TIGHT_COLLINEARITY_EPSILON_DEGS = 0.26
# NONCOLLINEARITY_EPSILON_DEGS: Used when we are going to trust the precision, even if seemingly collinear.
NONCOLLINEARITY_EPSILON_DEGS = 0.0

# DET_EPSILON: Epsilon to compare determinants during intersection computations from 2d cross products, in order
# to prevent division by 0.
DET_EPSILON = 1e-5
