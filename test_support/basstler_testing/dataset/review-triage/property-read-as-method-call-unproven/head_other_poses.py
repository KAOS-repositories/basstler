"""
Poses whose transform the sample computes with a method.
"""

from __future__ import annotations


class Transform:
    def __init__(self, entries: tuple[float, ...]) -> None:
        self.entries = entries


class SpatialPose:
    def __init__(self, coordinates: tuple[float, ...]) -> None:
        self.coordinates = coordinates

    def to_transform(self) -> Transform:
        return Transform(self.coordinates)

    def offset(self) -> float:
        return self.coordinates[0]


class PlanarPose:
    def __init__(self, coordinates: tuple[float, ...]) -> None:
        self.coordinates = coordinates

    def to_transform(self) -> Transform:
        return Transform((*self.coordinates, 1.0))
