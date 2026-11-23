"""
Shifting poses with a function from outside the repository.
"""

from __future__ import annotations

from outside import shift

from geometry.spatial import Pose


def shifted() -> Pose:
    return shift(Pose(), 1.0)
