"""
Setting the tool up.
"""

from __future__ import annotations

from tool.locations import PluginLocation


def setup_script() -> str:
    """
    :return: :attr:`PluginLocation.SETUP_SCRIPT`, as text.
    """
    return str(PluginLocation.SETUP_SCRIPT)
