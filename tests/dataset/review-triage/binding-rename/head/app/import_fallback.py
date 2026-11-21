"""
The spatial pose, imported from its module or else from the package's interface.
"""

from __future__ import annotations

try:
    from geometry.spatial import Pose3Dimensional
except ImportError:
    from geometry.api import Pose3Dimensional


def origin() -> Pose3Dimensional:
    return Pose3Dimensional()
