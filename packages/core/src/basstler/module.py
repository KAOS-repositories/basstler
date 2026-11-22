"""
A module of a Python package: its dotted name, and what it is relative to.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Self

from basstler.exceptions import ModuleOutsideRootError

SEPARATOR = "."
"""
What separates the parts of a dotted name, and marks a relative one when it leads.
"""


@dataclass(frozen=True, order=True)
class Module:
    """
    A module, a package or a subpackage, named by its dotted name, in its absolute form
    or relative to a root.
    """

    parts: tuple[str, ...]
    """
    The names between the dots, outermost package first, below :attr:`root` when there
    is one.
    """

    root: Module | None = None
    """
    The package :attr:`parts` lie below; none for an absolute module.
    """

    @classmethod
    def from_dotted_name(cls, dotted_name: str, root: Module | None = None) -> Self:
        """
        :param dotted_name: A module's name without a leading dot; empty for the module
            without parts.
        :param root: The package the name lies below; none for an absolute name.
        :return: The module it names.
        """
        return cls(tuple(dotted_name.split(SEPARATOR)) if dotted_name else (), root)

    def __str__(self) -> str:
        return f"{SEPARATOR if self.root else ''}{self.dotted_name}"

    @property
    def dotted_name(self) -> str:
        """
        The parts joined by dots, without the leading dot of a relative module.
        """
        return SEPARATOR.join(self.parts)

    @property
    def absolute(self) -> Module:
        """
        This module with its root's parts in front; itself when it has no root.
        """
        if self.root is None:
            return self
        return Module((*self.root.absolute.parts, *self.parts))

    @property
    def path(self) -> Path:
        """
        The parts as directories, below the root's directory and without a suffix.
        """
        return Path(*self.parts)

    @property
    def top_level_package(self) -> Self:
        """
        The outermost package holding the module, which is the first part of its
        absolute form.
        """
        return type(self)(self.absolute.parts[:1])

    def is_within(self, root: Module) -> bool:
        """
        :param root: A package, or any module.
        :return: Whether this module is *root* or lies under it, comparing whole parts.
        """
        return self.absolute.parts[: len(root.absolute.parts)] == root.absolute.parts

    def relative_to(self, root: Module) -> Self:
        """
        :param root: A package, or any module, that holds this module.
        :return: This module's name below *root*, which it keeps as its root.
        :raises ModuleOutsideRootError: When this module is not within *root*.
        """
        if not self.is_within(root):
            raise ModuleOutsideRootError(self, root)
        return type(self)(
            self.absolute.parts[len(root.absolute.parts) :], root.absolute
        )
