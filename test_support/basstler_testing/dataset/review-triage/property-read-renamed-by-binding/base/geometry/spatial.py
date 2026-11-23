"""
Poses in space.
"""

from __future__ import annotations

from geometry.matrices import Matrix


class Pose:
    """
    A position with an orientation.
    """

    @property
    def transform(self) -> Matrix:
        """
        The transform placing a frame at the pose.
        """
        return Matrix(self)
