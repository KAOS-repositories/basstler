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

    SETUP_SCRIPT = HOOKS + "/setup.sh"
    """
    The script setting the tool up.
    """

    SAVE_SCRIPT = HOOKS + "/save.sh"
    """
    The script saving the notes.
    """

    @property
    def file_name(self) -> str:
        """
        The script's name, without its directory.
        """
        return self.value.rpartition("/")[2]
