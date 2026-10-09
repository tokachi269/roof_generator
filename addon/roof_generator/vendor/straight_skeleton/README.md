# Bundled straight skeleton source

Source: `py_straight_skeleton` version 0.1.0, BSD-3-Clause, copyright ICON.
The original license accompanies the source and is included in the addon ZIP.

Only the five algorithm/math modules and the public constructor are bundled.
Plotting and development dependencies are excluded. Imports are relative to
this private package; the constructor exposes the pinned version directly
instead of querying an installed wheel's metadata. The algorithm and its
tolerances are unchanged. Face traversal additionally rejects a repeated
directed arc instead of looping indefinitely on invalid incidence.
No runtime pip installation or external package is
required.

This dependency supplies topology incidence and initial XY. Its event times
and XYZ are not geometry constraints. Unresolved events and invalid incidence
must fail explicitly; they must not activate an alternate generator, jitter,
mesh repair or solver topology discovery.
