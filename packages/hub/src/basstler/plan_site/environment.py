"""
The environment variables the plan site reads.
"""

from __future__ import annotations

from enum import StrEnum

from basstler.locations import BasstlerShellVariable


class SiteBasstlerVariable(BasstlerShellVariable):
    """
    The shell configuration's variables the plan site reads.
    """

    PYTHON = "BASSTLER_PYTHON"
    """
    The interpreter whose environment holds this package, for running its modules.
    """


class UserDirectoryVariable(StrEnum):
    """
    The variables naming a user's own directories.
    """

    CONFIGURATION_HOME = "XDG_CONFIG_HOME"
    """
    Where programs read the user's configuration from, ``~/.config`` when unset.
    """

    SEARCH_PATH = "PATH"
    """
    The directories executables are found in.
    """
