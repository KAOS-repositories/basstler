"""
A joint pose built before the spatial pose is imported over it.
"""

from __future__ import annotations

from robot.types import *

JOINT_ORIGIN = Pose3Dimensional()

from geometry.spatial import Pose3Dimensional


def origin() -> Pose3Dimensional:
    return Pose3Dimensional()
