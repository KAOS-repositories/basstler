from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Pose3Dimensional:
    """
    A position and heading in space.
    """

    x: float
    y: float
    z: float
    yaw: float

    def shifted(self, dx: float, dy: float, dz: float) -> Pose3Dimensional:
        """
        :return: This pose moved by the given offsets.
        """
        return Pose3Dimensional(self.x + dx, self.y + dy, self.z + dz, self.yaw)


@dataclass
class Line:
    """
    A straight line between two poses.
    """

    start: Pose3Dimensional
    end: Pose3Dimensional
