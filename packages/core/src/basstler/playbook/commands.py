"""
The names of the ``basstler skills`` commands.
"""

from __future__ import annotations

from enum import StrEnum

from basstler.locations import PackageLocation


class SkillsCommand(StrEnum):
    """
    The ``basstler skills`` command group and its commands, by name.
    """

    GROUP = "skills"
    """
    The command group itself.
    """

    BUILD = "build"
    """
    Write the plugin's generated files and check its skills against the playbook.
    """

    @property
    def invocation(self) -> str:
        """
        The command line running this command.
        """
        return f"{PackageLocation.DIRECTORY.name} {SkillsCommand.GROUP} {self}"
