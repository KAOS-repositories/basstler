"""
The environment variables the plan site reads.
"""

from __future__ import annotations

from basstler.environment import EnvironmentVariable


class SiteBasstlerVariable(EnvironmentVariable):
    """
    The variables this package's own shell configuration sets that the plan site reads.
    """

    PYTHON = "BASSTLER_PYTHON"
    """
    The interpreter whose environment holds this package, for running its modules.
    """
