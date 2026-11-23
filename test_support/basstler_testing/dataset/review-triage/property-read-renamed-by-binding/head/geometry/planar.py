"""
Poses of a robot's joints in a plane.
"""

from __future__ import annotations

from geometry.matrices import Matrix3Dimensional


class PlanarPose:
    """
    A position with an orientation in a plane.
    """

    def transform(self) -> Matrix3Dimensional:
        return Matrix3Dimensional(self)
