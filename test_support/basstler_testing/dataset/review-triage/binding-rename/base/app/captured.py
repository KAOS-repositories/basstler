from __future__ import annotations

from geometry.spatial import Pose

ORIGIN = Pose()


def both() -> tuple[object, object]:
    class Pose3Dimensional:
        pass

    return Pose(), Pose3Dimensional()
