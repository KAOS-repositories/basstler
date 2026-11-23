"""
Placing frames at poses.
"""

from __future__ import annotations

from geometry.matrices import Matrix
from geometry.spatial import Pose


def placement(pose: Pose) -> Matrix:
    return pose.transform
