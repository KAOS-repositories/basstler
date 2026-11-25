"""
Shapes measured on a plane.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Rectangle:
    width: float
    height: float

    def area(self) -> float:
        return self.width * self.height

    def perimeter(self) -> float:
        """
        The length of the rectangle's outline.
        """
        return 2 * (self.width + self.height)
