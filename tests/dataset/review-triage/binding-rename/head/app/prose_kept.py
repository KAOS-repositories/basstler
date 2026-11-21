"""
Targets for the gripper.
"""

from __future__ import annotations

from geometry.spatial import Pose3Dimensional


def target() -> Pose3Dimensional:
    """
    :return: Pose of the target, in the world frame.
    """
    return Pose3Dimensional()
