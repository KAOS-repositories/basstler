"""
The spatial pose imported, then joint poses imported wholesale over it.
"""

from __future__ import annotations

from geometry.spatial import Pose
from robot.types import *


def origin() -> Pose:
    return Pose()
