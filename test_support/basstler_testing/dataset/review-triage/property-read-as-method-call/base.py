"""
Reading a pose's matrix.
"""

from __future__ import annotations

from other_poses import Matrix, Pose


def placement(pose: Pose) -> Matrix:
    return pose.as_matrix


def entries(pose: Pose) -> tuple[float, ...]:
    return pose.as_matrix.entries
