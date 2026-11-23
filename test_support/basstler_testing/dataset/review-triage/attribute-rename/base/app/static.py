"""
A static helper whose first parameter is called self.
"""

from __future__ import annotations

from shapes.vector import Vector


class Helper(Vector):
    """
    Helpers over vectors.
    """

    @staticmethod
    def norm_of(self: Vector) -> float:
        """
        :param self: Any vector.
        :return: Its squared length.
        """
        return self.norm_squared()
