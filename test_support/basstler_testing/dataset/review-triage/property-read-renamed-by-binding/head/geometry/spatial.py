"""
Poses in space.
"""

from __future__ import annotations

from geometry.matrices import Matrix3Dimensional


class Pose3Dimensional:
    """
    A position with an orientation.
    """

    def transform(self) -> Matrix3Dimensional:
        return Matrix3Dimensional(self)
