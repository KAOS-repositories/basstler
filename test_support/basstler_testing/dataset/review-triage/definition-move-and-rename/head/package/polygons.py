from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RegularSquare:
    """
    A square with a corner at the origin.
    """

    side: float

    def area(self) -> float:
        """
        :return: The surface it covers.
        """
        return self.side**2

    def doubled(self) -> RegularSquare:
        """
        :return: A square with sides twice as long.
        """
        return RegularSquare(self.side * 2)
