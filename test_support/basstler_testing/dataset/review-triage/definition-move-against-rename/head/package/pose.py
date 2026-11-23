from __future__ import annotations

from abc import ABC, abstractmethod


class Pose(ABC):
    """
    Anything with a position and a heading.
    """

    @abstractmethod
    def shifted(self, dx: float, dy: float, dz: float) -> Pose:
        """
        :return: This pose moved by the given offsets.
        """
