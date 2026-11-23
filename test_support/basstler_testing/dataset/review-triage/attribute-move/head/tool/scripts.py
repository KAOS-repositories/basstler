"""
Every script of the plugin.
"""

from __future__ import annotations

from tool.locations import PluginLocation
from tool.setup_locations import SetupPluginLocation


def scripts() -> tuple[str, ...]:
    """
    :return: The plugin's scripts.
    """
    return (SetupPluginLocation.SETUP_SCRIPT, PluginLocation.SAVE_SCRIPT)
