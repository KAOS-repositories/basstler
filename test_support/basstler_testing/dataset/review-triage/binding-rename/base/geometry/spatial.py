"""
Poses in space.
"""

from __future__ import annotations


class Pose:
    """
    A position with an orientation.
    """

    def moved(self, offset: float) -> Pose:
        """
        :param offset: How far to move.
        :return: This Pose moved by *offset*.
        """
        return Pose()
