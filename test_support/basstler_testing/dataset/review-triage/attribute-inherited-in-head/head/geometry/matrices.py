"""
Transformations of space.
"""

from __future__ import annotations


class Transform:
    """
    A transformation of space.
    """

    def dot(self, other: object) -> object:
        """
        :return: The other value, transformed.
        """
        return other


class Rotation(Transform):
    """
    A rotation of space.
    """

    def rotation_matrix(self) -> Rotation:
        """
        :return: The rotation as a matrix.
        """
        return self
