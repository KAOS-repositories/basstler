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

    def scaled_squared_length(self) -> float:
        """
        :return: The squared length, scaled.
        """
        return self.factor * self.squared_length()

    def report(self) -> str:
        """
        :return: The caption and the length.
        """
        return f"{self.caption}: {self.scaled_squared_length()}"
