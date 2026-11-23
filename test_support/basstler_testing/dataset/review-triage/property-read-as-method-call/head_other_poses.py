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
        """
        The transform placing a frame at the pose.
        """
        return Transform(self.coordinates)
