"""
Poses whose matrix the sample reads as a property.
"""

from __future__ import annotations


class Matrix:
    def __init__(self, entries: tuple[float, ...]) -> None:
        self.entries = entries


class Pose:
    def __init__(self, coordinates: tuple[float, ...]) -> None:
        self.coordinates = coordinates

    @property
    def as_matrix(self) -> Matrix:
        """
        The pose as a matrix.
        """
        return Matrix(self.coordinates)
