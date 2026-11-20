from __future__ import annotations
from geometry.spatial import Pose3Dimensional


def gripper() -> Pose3Dimensional:
    return Pose3Dimensional()


def robot_home() -> object:
    class Pose:
        pass

    return Pose()
