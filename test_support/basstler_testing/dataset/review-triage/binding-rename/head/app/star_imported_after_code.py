"""
Joint poses imported wholesale, then a setting, then the spatial pose.
"""

from __future__ import annotations

from robot.types import *

SPEED = 1.0

from geometry.spatial import Pose3Dimensional


def origin() -> Pose3Dimensional:
    return Pose3Dimensional()
