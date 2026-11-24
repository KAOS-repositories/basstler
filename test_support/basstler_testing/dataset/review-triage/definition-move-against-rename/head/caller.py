from __future__ import annotations

from package.geometry import Line, Pose3Dimensional

ORIGIN = Pose3Dimensional(0.0, 0.0, 0.0, 0.0)
UP = Line(ORIGIN, ORIGIN.shifted(0.0, 0.0, 1.0))
