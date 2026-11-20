"""
Planning motions between poses.
"""

from __future__ import annotations

from geometry.spatial import Pose

# A Pose the gripper starts from.
START = Pose()


def plan(goal: Pose) -> list[Pose]:
    """
    :param goal: The Pose to reach.
    :return: The poses on the way.
    """
    return [START, goal]
