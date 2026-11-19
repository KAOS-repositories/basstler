"""
Polygons.
"""

from __future__ import annotations


class Polygon:
    """
    A polygon, whose area its subclasses compute.
    """

    def area(self) -> float:
        """
        :return: The area.
        """
        return 0.0

    def is_empty(self) -> bool:
        """
        :return: Whether the area is zero.
        """
        return self.area() == 0.0
