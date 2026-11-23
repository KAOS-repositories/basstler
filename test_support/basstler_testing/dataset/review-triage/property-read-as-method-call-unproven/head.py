"""
Reading the matrices and offsets of poses.
"""

from __future__ import annotations

from other_poses import PlanarPose, SpatialPose, Transform


def planar_placement(pose: PlanarPose) -> Transform:
    return pose.to_transform()


def any_placements(pose):
    return [pose.to_transform()]


def shift(pose: SpatialPose):
    return pose.offset()
