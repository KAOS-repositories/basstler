"""
The files setting the tool up.
"""

from __future__ import annotations

from enum import Enum

from tool.locations import PluginLocation


class SetupPluginLocation(Enum):
    """
    A file of the plugin that sets the tool up.
    """

    SETUP_SCRIPT = PluginLocation.HOOKS + "/setup.sh"
    """
    The script setting the tool up.
    """
