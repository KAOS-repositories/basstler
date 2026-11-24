"""
Reading a pose's matrix.
"""

from __future__ import annotations

from other_poses import SpatialPose, Transform


def placement(pose: SpatialPose) -> Transform:
    return pose.to_transform()


def entries(pose: SpatialPose) -> tuple[float, ...]:
    return pose.to_transform().entries
