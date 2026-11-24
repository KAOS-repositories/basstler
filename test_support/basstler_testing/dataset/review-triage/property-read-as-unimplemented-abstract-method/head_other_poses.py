"""
Poses whose transform only an abstract method of their metaclass-checked base declares.
"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod


class Transform:
    def __init__(self, entries: tuple[float, ...]) -> None:
        self.entries = entries


class Placeable(metaclass=ABCMeta):
    @abstractmethod
    def to_transform(self) -> Transform:
        """
        The transform placing a frame at the object.
        """


class SpatialPose(Placeable):
    def __init__(self, coordinates: tuple[float, ...]) -> None:
        self.coordinates = coordinates
