"""
Closed shapes.
"""

from __future__ import annotations


class Shape:
    """
    A closed shape.
    """

    def perimeter(self) -> float:
        """
        :return: The length of the shape's boundary.
        """
        return 0.0

    def describe(self) -> str:
        """
        :return: A description.
        """
        return f"perimeter {self.perimeter()}"
