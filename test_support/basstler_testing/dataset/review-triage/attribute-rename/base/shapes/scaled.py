"""
Vectors scaled by a factor.
"""

from __future__ import annotations

from shapes.vector import Vector


class ScaledVector(Vector):
    """
    A vector with a factor.
    """

    factor: float = 1.0

    def scaled_norm_squared(self) -> float:
        """
        :return: The squared length, scaled.
        """
        return self.factor * self.norm_squared()

    def report(self) -> str:
        """
        :return: The tag and the length.
        """
        return f"{self.tag}: {self.scaled_norm_squared()}"
