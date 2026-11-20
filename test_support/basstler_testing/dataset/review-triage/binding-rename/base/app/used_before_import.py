"""
A joint pose built before the spatial pose is imported over it.
"""

from __future__ import annotations

from robot.types import *

JOINT_ORIGIN = Pose()

from geometry.spatial import Pose


def origin() -> Pose:
    return Pose()
