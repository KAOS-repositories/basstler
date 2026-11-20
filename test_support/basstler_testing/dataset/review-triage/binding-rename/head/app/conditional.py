from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geometry.spatial import Pose3Dimensional
else:
    from robot.types import Pose3Dimensional


def origin() -> Pose3Dimensional:
    return Pose3Dimensional()
