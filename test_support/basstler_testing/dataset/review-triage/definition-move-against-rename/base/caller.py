from __future__ import annotations

from package.geometry import Line, Pose

ORIGIN = Pose(0.0, 0.0, 0.0, 0.0)
UP = Line(ORIGIN, ORIGIN.shifted(0.0, 0.0, 1.0))
