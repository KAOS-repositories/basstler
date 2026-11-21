"""
Joint poses imported wholesale, the spatial pose imported after them.
"""

from __future__ import annotations

from robot.types import *
from geometry.spatial import Pose3Dimensional


def origin() -> Pose3Dimensional:
    return Pose3Dimensional()
