"""
The robot's own types.
"""

from __future__ import annotations


class Pose:
    """
    A pose of a robot joint.
    """


class Matrix:
    """
    A matrix of a robot joint.
    """

    def __init__(self, entries: object) -> None:
        self.entries = entries
