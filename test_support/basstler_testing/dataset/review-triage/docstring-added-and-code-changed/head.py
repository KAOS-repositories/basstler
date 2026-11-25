"""
Shapes measured on a plane.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Rectangle:
    """
    A rectangle with sides parallel to the axes.
    """

    width: float
    """
    The extent along the x axis.
    """
    height: float

    def area(self) -> float:
        """
        The surface the rectangle covers.
        """
        return self.width * self.height * 2

    def perimeter(self) -> float:
        return 2 * (self.width + self.height)
