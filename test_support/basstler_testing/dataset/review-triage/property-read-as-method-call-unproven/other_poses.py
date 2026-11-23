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
        return Matrix(self.coordinates)

    def offset(self) -> float:
        return self.coordinates[0]


class PlanarPose:
    def __init__(self, coordinates: tuple[float, ...]) -> None:
        self.coordinates = coordinates

    @property
    def as_matrix(self) -> Matrix:
        return Matrix((*self.coordinates, 0.0))
