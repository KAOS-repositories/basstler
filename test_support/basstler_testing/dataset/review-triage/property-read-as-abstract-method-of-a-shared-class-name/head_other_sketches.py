"""
Sketches of a placeable thing, sharing the name of the poses' abstract base class.
"""

from __future__ import annotations


class Placeable:
    def outline(self) -> tuple[float, ...]:
        """
        The points the sketch is drawn through.
        """
        return ()
