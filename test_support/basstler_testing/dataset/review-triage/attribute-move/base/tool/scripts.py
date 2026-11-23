"""
Every script of the plugin.
"""

from __future__ import annotations

from tool.locations import PluginLocation


def scripts() -> tuple[str, ...]:
    """
    :return: The plugin's scripts.
    """
    return (PluginLocation.SETUP_SCRIPT, PluginLocation.SAVE_SCRIPT)
