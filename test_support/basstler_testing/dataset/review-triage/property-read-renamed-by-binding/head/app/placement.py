"""
Placing frames at poses.
"""

from __future__ import annotations

from geometry.matrices import Matrix3Dimensional
from geometry.spatial import Pose3Dimensional


def placement(pose: Pose3Dimensional) -> Matrix3Dimensional:
    return pose.transform()
