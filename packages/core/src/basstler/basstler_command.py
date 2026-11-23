"""
The commands of a ``basstler`` command group, by name.
"""

from __future__ import annotations

from abc import abstractmethod
from enum import StrEnum

from basstler.class_property import classproperty
from basstler.locations import PackageLocation


class BasstlerCommand(StrEnum):
    """
    A command of one ``basstler`` command group, by the word that invokes it after the
    group's name.
    """

    @classproperty
    @abstractmethod
    def group(cls) -> str:
        """
        The word that invokes the command group after ``basstler``.
        """

    @property
    def invocation(self) -> str:
        """
        The command line running this command.
        """
        return f"{PackageLocation.DIRECTORY.name} {self.group} {self}"
