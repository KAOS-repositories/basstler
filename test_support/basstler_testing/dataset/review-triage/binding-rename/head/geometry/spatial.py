"""
Poses in space.
"""

from __future__ import annotations


class Pose3Dimensional:
    """
    A position with an orientation.
    """

    def moved(self, offset: float) -> Pose3Dimensional:
        """
        :param offset: How far to move.
        :return: This Pose3Dimensional moved by *offset*.
        """
        return Pose3Dimensional()
