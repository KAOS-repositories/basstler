"""
The names of the ``basstler code-modification`` command group and its commands.
"""

from __future__ import annotations

from enum import StrEnum


class CodeModificationCommand(StrEnum):
    """
    The ``basstler code-modification`` command group and its commands, by name.
    """

    GROUP = "code-modification"
    """
    The command group itself.
    """

    RENAME = "rename"
    """
    Rename a symbol in every Python file given.
    """

    RELOCATE_IMPORT = "relocate-import"
    """
    Import a name from the module it moved to in every Python file given.
    """
