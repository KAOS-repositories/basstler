"""
The spatial pose imported, then helpers that bind no pose imported wholesale.
"""

from __future__ import annotations

from geometry.spatial import Pose
from robot.helpers import *


def origin() -> Pose:
    return Pose()
