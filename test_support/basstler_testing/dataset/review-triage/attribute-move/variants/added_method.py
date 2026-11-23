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

    SETUP_SCRIPT = PluginLocation.HOOKS + "/setup.sh"
    """
    The script setting the tool up.
    """

    def __str__(self) -> str:
        """
        :return: The file's name, without its directory.
        """
        return self.value.rpartition("/")[2]
