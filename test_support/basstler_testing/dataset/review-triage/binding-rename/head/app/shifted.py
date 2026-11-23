"""
Shifting poses with a function from outside the repository.
"""

from __future__ import annotations

from outside import shift

from geometry.spatial import Pose3Dimensional


def shifted() -> Pose3Dimensional:
    return shift(Pose3Dimensional(), offset=1.0)
