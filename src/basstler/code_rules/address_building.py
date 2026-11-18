"""
Finds addresses appended to a repository's own address by hand, outside the class that
builds every address within a repository.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import override

from basstler.code_rules.checker import CodeRuleChecker, CodeRuleViolation
from basstler.locations import PackageLocation

# %% what is an address


class RepositoryAddress(StrEnum):
    """
    The attributes of a repository whose value is an address more is appended to.
    """

    API_PATH = "api_path"
    """
    The repository's REST path.
    """

    URL = "url"
    """
    The repository's page.
    """

    SETTINGS_URL = "settings_url"
    """
    The repository's settings page.
    """


# %% the checker


@dataclass(frozen=True)
class HandBuiltAddressChecker(CodeRuleChecker):
    """
    Reports every f-string of the package that starts with a repository's address and
    appends a path to it, outside :attr:`PackageLocation.GITHUB_REPOSITORY_MODULE`;
    tests spell the addresses they pin.
    """

    package_directory: Path = PackageLocation.DIRECTORY
    """
    The directory whose sources are checked.
    """

    @override
    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        source = path.resolve()
        if source == PackageLocation.GITHUB_REPOSITORY_MODULE.resolve():
            return
        if not source.is_relative_to(self.package_directory.resolve()):
            return
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.JoinedStr) and self.appends_to_an_address(node):
                yield CodeRuleViolation(
                    path,
                    node.lineno,
                    node.end_lineno or node.lineno,
                    "an address built by hand on a repository's address; build it "
                    "with a method of the class of what it addresses, such as "
                    "Repository",
                )

    @staticmethod
    def appends_to_an_address(text: ast.JoinedStr) -> bool:
        """
        :param text: An f-string.
        :return: Whether it starts with a repository's address and continues with a
            path below it.
        """
        if len(text.values) < 2:
            return False
        first, second = text.values[0], text.values[1]
        return (
            isinstance(first, ast.FormattedValue)
            and isinstance(first.value, ast.Attribute)
            and first.value.attr in set(RepositoryAddress)
            and isinstance(second, ast.Constant)
            and isinstance(second.value, str)
            and second.value.startswith("/")
        )
