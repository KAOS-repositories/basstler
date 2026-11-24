"""
Matrices placing frames in space.
"""

from __future__ import annotations


class Matrix3Dimensional:
    """
    A homogeneous transformation.
    """

    def __init__(self, entries: object) -> None:
        self.entries = entries
