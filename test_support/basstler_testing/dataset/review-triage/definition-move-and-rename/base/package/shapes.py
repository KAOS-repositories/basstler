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


@dataclass
class Square:
    """
    A square with a corner at the origin.
    """

    side: float

    def area(self) -> float:
        """
        :return: The surface it covers.
        """
        return self.side**2

    def doubled(self) -> Square:
        """
        :return: A square with sides twice as long.
        """
        return Square(self.side * 2)
