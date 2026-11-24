"""
Reading the matrices and offsets of poses.
"""

from __future__ import annotations

from other_poses import Matrix, PlanarPose, Pose


def planar_placement(pose: PlanarPose) -> Matrix:
    return pose.as_matrix


def any_placements(pose):
    return [pose.as_matrix]


def shift(pose: Pose):
    return pose.offset
