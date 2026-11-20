"""
Squares.
"""

from __future__ import annotations

from shapes.polygon import Polygon


class Square(Polygon):
    """
    A square of a side.
    """

    side: float = 1.0

    def area(self) -> float:
        """
        :return: The square of the side.
        """
        return self.side * self.side
