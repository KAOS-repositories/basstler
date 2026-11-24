"""
Turning points.
"""

from __future__ import annotations

from geometry.matrices import Rotation


def turned(point: object) -> object:
    """
    :return: The point, rotated.
    """
    return Rotation().dot(point)
