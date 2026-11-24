"""
Setting the tool up.
"""

from __future__ import annotations

from tool.setup_locations import SetupPluginLocation


def setup_script() -> str:
    """
    :return: :attr:`SetupPluginLocation.SETUP_SCRIPT`, as text.
    """
    return str(SetupPluginLocation.SETUP_SCRIPT)
