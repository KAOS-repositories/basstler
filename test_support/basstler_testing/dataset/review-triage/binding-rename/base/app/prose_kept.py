"""
Targets for the gripper.
"""

from __future__ import annotations

from geometry.spatial import Pose


def target() -> Pose:
    """
    :return: Pose of the target, in the world frame.
    """
    return Pose()
