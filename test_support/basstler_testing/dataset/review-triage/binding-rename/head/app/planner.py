"""
Planning motions between poses.
"""

from __future__ import annotations

from geometry.spatial import Pose3Dimensional

# A Pose3Dimensional the gripper starts from.
START = Pose3Dimensional()


def plan(goal: Pose3Dimensional) -> list[Pose3Dimensional]:
    """
    :param goal: The Pose3Dimensional to reach.
    :return: The poses on the way.
    """
    return [START, goal]
