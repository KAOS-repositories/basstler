"""
The environment variables the plan site reads.
"""

from __future__ import annotations

from basstler.locations import BasstlerShellVariable


class SiteBasstlerVariable(BasstlerShellVariable):
    """
    The shell configuration's variables the plan site reads.
    """

    PYTHON = "BASSTLER_PYTHON"
    """
    The interpreter whose environment holds this package, for running its modules.
    """
