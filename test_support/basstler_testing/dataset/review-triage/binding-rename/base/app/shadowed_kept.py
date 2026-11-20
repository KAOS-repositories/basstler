from __future__ import annotations
from geometry.spatial import Pose


def gripper() -> Pose:
    return Pose()


def robot_home() -> object:
    class Pose:
        pass

    return Pose()
