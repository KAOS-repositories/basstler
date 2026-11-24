"""
Poses of a robot's joints in a plane.
"""

from __future__ import annotations

from robot.types import Matrix


class PlanarPose:
    """
    A position with an orientation in a plane.
    """

    @property
    def transform(self) -> Matrix:
        return Matrix(self)
