"""
Poses whose transform the sample computes with a method an abstract interface declares.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Transform:
    def __init__(self, entries: tuple[float, ...]) -> None:
        self.entries = entries


class Placeable(ABC):
    @abstractmethod
    def to_transform(self) -> Transform:
        """
        The transform placing a frame at the object.
        """


class SpatialPose(Placeable):
    def __init__(self, coordinates: tuple[float, ...]) -> None:
        self.coordinates = coordinates

    def to_transform(self) -> Transform:
        """
        The transform placing a frame at the pose.
        """
        return Transform(self.coordinates)
