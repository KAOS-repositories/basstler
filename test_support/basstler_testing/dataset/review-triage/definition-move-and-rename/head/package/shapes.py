from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Circle:
    """
    A circle around the origin.
    """

    radius: float

    def area(self) -> float:
        """
        :return: The surface it covers.
        """
        return 3.14159 * self.radius**2
