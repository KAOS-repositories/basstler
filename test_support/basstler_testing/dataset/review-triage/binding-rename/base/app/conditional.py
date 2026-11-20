from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geometry.spatial import Pose
else:
    from robot.types import Pose


def origin() -> Pose:
    return Pose()
