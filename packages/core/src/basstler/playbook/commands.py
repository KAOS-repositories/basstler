"""
The names of the ``basstler skills`` commands.
"""

from __future__ import annotations


from basstler.basstler_command import BasstlerCommand
from basstler.class_property import classproperty


class SkillsCommand(BasstlerCommand):
    """
    The ``basstler skills`` command group and its commands, by name.
    """

    @classproperty
    def group(cls) -> str:
        return "skills"

    BUILD = "build"
    """
    Write the plugin's generated files and check its skills against the playbook.
    """
