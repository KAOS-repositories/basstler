"""
Links one document from another by its relative path.
"""

from __future__ import annotations

import os

from basstler.locations import ProjectLocation


def plans_link(directory: str) -> str:
    """
    :return: The path of the plans directory relative to *directory*.
    """
    return os.path.relpath(ProjectLocation.PLANS, directory)
