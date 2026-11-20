from __future__ import annotations

from geometry.spatial import Pose3Dimensional

ORIGIN = Pose3Dimensional()


def both() -> tuple[object, object]:
    class Pose3Dimensional:
        pass

    return Pose3Dimensional(), Pose3Dimensional()
