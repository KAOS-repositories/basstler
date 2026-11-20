from __future__ import annotations
from geometry.spatial import Pose3Dimensional

POSE_CLASS = "Pose3Dimensional"


def make() -> Pose3Dimensional:
    return Pose3Dimensional()
