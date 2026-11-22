"""
A module of a Python package: its dotted name, and what it is relative to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from basstler.exceptions import ModuleOutsideRootError

SEPARATOR = "."
"""
What separates the parts of a dotted name.
"""


@dataclass(frozen=True, order=True)
class Module:
    """
    A module, a package or a subpackage, named by its dotted name.
    """

    parts: tuple[str, ...]
    """
    The names between the dots, outermost package first.
    """

    @classmethod
    def from_dotted_name(cls, dotted_name: str) -> Self:
        """
        :param dotted_name: A module's name as an import statement spells it; empty for
            the module without parts.
        :return: The module it names.
        """
        return cls(tuple(dotted_name.split(SEPARATOR)) if dotted_name else ())

    def __str__(self) -> str:
        return SEPARATOR.join(self.parts)

    @property
    def top_level_package(self) -> Self:
        """
        The outermost package holding the module, which is its first part.
        """
        return type(self)(self.parts[:1])

    def is_within(self, root: Module) -> bool:
        """
        :param root: A package, or any module.
        :return: Whether this module is *root* or lies under it, comparing whole parts.
        """
        return self.parts[: len(root.parts)] == root.parts

    def relative_to(self, root: Module) -> Self:
        """
        :param root: A package, or any module, that holds this module.
        :return: This module's name below *root*.
        :raises ModuleOutsideRootError: When this module is not within *root*.
        """
        if not self.is_within(root):
            raise ModuleOutsideRootError(self, root)
        return type(self)(self.parts[len(root.parts) :])
