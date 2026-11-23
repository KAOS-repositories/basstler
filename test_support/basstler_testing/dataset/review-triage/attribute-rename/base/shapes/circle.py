"""
Circles.
"""

from __future__ import annotations

from shapes.shape import Shape


class Circle(Shape):
    """
    A circle of a radius.
    """

    radius: float = 1.0

    def perimeter(self) -> float:
        """
        :return: The circumference.
        """
        return 2 * 3.14159 * self.radius
