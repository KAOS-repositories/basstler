"""
The spatial pose imported, then helpers that bind no pose imported wholesale.
"""

from __future__ import annotations

from geometry.spatial import Pose3Dimensional
from robot.helpers import *


def origin() -> Pose3Dimensional:
    return Pose3Dimensional()
