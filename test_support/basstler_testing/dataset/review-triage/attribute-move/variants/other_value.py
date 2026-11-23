"""
The files setting the tool up.
"""

from __future__ import annotations

from enum import StrEnum

from tool.locations import PluginLocation


class SetupPluginLocation(StrEnum):
    """
    A file of the plugin that sets the tool up.
    """

    SETUP_SCRIPT = PluginLocation.HOOKS + "/install.sh"
    """
    The script setting the tool up.
    """
