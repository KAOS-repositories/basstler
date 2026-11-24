"""
The files the tool names.
"""

from __future__ import annotations

from enum import StrEnum


class PluginLocation(StrEnum):
    """
    A file of the plugin.
    """

    HOOKS = "hooks"
    """
    The hook scripts.
    """

    SAVE_SCRIPT = HOOKS + "/save.sh"
    """
    The script saving the notes.
    """
