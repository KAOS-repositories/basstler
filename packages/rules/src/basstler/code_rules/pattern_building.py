"""
Finds regular expressions written as pattern text, outside the module that builds every
pattern from named parts.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import override

from basstler.code_rules.checker import CodeRuleChecker, CodeRuleViolation
from basstler.locations import PackageLocation
from basstler.text_file import TextFile

# %% what reads pattern text


class PatternFunction(StrEnum):
    """
    The functions of :mod:`re` that take a pattern as text.
    """

    COMPILE = "compile"
    """
    Compiles a pattern.
    """

    MATCH = "match"
    """
    Matches a pattern at the start of a text.
    """

    FULLMATCH = "fullmatch"
    """
    Matches a pattern against a whole text.
    """

    SEARCH = "search"
    """
    Finds a pattern's first match in a text.
    """

    FINDALL = "findall"
    """
    Finds every match of a pattern in a text.
    """

    FINDITER = "finditer"
    """
    Iterates over every match of a pattern in a text.
    """

    SUB = "sub"
    """
    Replaces every match of a pattern.
    """

    SUBN = "subn"
    """
    Replaces every match of a pattern and counts them.
    """

    SPLIT = "split"
    """
    Splits a text at every match of a pattern.
    """

    ESCAPE = "escape"
    """
    Writes a text as the pattern matching only itself.
    """


# %% the checker


@dataclass(frozen=True)
class HandWrittenPatternChecker(CodeRuleChecker):
    """
    Reports every use of a :class:`PatternFunction` outside the modules allowed one.
    """

    allowed_modules: tuple[Path, ...] = (
        PackageLocation.REGULAR_EXPRESSION_MODULE,
        PackageLocation.UPSTREAM_REVIEWS_FETCH,
    )
    """
    The module building every pattern, and the program that can import nothing of the
    package and compiles a pattern the package built.
    """

    @override
    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        if path.resolve() in {module.resolve() for module in self.allowed_modules}:
            return
        for node in ast.walk(ast.parse(TextFile(path).read())):
            if self.reads_pattern_text(node):
                yield CodeRuleViolation(
                    path,
                    node.lineno,
                    node.end_lineno or node.lineno,
                    "a pattern written as regular expression text; build it from "
                    "named parts with basstler.regular_expression",
                )

    @staticmethod
    def reads_pattern_text(node: ast.AST) -> bool:
        """
        :param node: A node of a module's syntax tree.
        :return: Whether it reads a :class:`PatternFunction` off :mod:`re`, or imports
            one from it.
        """
        functions = set(PatternFunction)
        if isinstance(node, ast.ImportFrom):
            return node.module == re.__name__ and any(
                alias.name in functions for alias in node.names
            )
        return (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == re.__name__
            and node.attr in functions
        )
