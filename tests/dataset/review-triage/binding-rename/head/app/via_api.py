from __future__ import annotations
from geometry.api import Pose3Dimensional as GeometryPose


def origin() -> GeometryPose:
    return GeometryPose()
