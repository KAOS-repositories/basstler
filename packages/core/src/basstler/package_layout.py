"""
What this package contains, read from every installed distribution's part of it and from
each module's own source rather than listed.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from basstler.locations import INSTALLED_PACKAGE


@dataclass(frozen=True)
class PackageModule:
    """
    One module of this package.
    """

    name: str
    """
    The module's dotted name within the package, e.g. ``"stack.model"``.
    """

    is_command_line_entry_point: bool
    """
    Whether the module guards a block on being run as ``__main__``, which is what makes
    ``python3 -m`` with :attr:`command_path` and ``--help`` answer rather than do
    nothing.
    """

    @property
    def import_path(self) -> str:
        """:return: The dotted path this module is imported by."""
        return f"basstler.{self.name}"

    @property
    def command_path(self) -> str:
        """
        :return: The dotted path ``python3 -m`` runs this module by: its subpackage's, for
            a subpackage's ``__main__`` module.
        """
        return self.import_path.removesuffix(".__main__")


def _has_a_main_block(source: Path) -> bool:
    """
    :param source: A module's file.
    :return: Whether it guards a top-level block on being run as ``__main__``.
    """
    return any(
        isinstance(node, ast.If) and "__main__" in ast.dump(node.test)
        for node in ast.parse(source.read_text(encoding="utf-8")).body
    )


@cache
def package_modules() -> tuple[PackageModule, ...]:
    """
    :return: Every module in every installed part of this package, in name order.
    """
    return tuple(
        sorted(
            (
                PackageModule(
                    ".".join(path.relative_to(directory).with_suffix("").parts),
                    _has_a_main_block(path),
                )
                for directory in INSTALLED_PACKAGE.directories
                for path in directory.rglob("*.py")
                if path.stem != "__init__"
            ),
            key=lambda module: module.name,
        )
    )


def command_line_entry_points() -> tuple[PackageModule, ...]:
    """
    :return: The modules a script or a session invokes directly.
    """
    return tuple(
        module for module in package_modules() if module.is_command_line_entry_point
    )
