"""
Polygons.
"""

from __future__ import annotations


class Polygon:
    """
    A polygon, whose area its subclasses compute.
    """

    def surface(self) -> float:
        """
        :return: The area.
        """
        return 0.0

    def is_empty(self) -> bool:
        """
        :return: Whether the area is zero.
        """
        return self.surface() == 0.0
