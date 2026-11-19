"""
The spatial pose, imported from its module or else from the package's interface.
"""

from __future__ import annotations

try:
    from geometry.spatial import Pose
except ImportError:
    from geometry.api import Pose


def origin() -> Pose:
    return Pose()
