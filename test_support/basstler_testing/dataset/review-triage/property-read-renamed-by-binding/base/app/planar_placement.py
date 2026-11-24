"""
Placing frames at the poses of joints.
"""

from __future__ import annotations

from geometry.planar import PlanarPose


def placement(pose: PlanarPose) -> object:
    return pose.transform
