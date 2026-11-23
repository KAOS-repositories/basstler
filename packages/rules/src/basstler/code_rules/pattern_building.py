"""
Finds regular expressions written as pattern text, outside the module that builds every
pattern from named parts.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import override

from libcst import matchers

from basstler.class_property import classproperty
from basstler.code_modification.patterns import CodePattern
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.references import ReferenceTo
from basstler.code_rules.checker import CodeRuleViolation
from basstler.code_rules.syntax_tree_checker import SyntaxTreeChecker
from basstler.locations import PackageLocation

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


class PatternTextCall(CodePattern):
    """
    A call of a :class:`PatternFunction`, whichever way the file imports :mod:`re`.
    """

    @classproperty
    def matcher(cls) -> matchers.Call:
        return matchers.Call(
            func=matchers.OneOf(
                *(
                    ReferenceTo(f"{re.__name__}.{function}").matcher
                    for function in PatternFunction
                )
            )
        )


@dataclass(frozen=True)
class HandWrittenPatternChecker(SyntaxTreeChecker):
    """
    Reports every call of a :class:`PatternFunction` outside the modules allowed one.
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
    def violations_of_module(
        self, path: Path, module: PositionedModule
    ) -> Iterator[CodeRuleViolation]:
        if path.resolve() in {allowed.resolve() for allowed in self.allowed_modules}:
            return
        for occurrence in PatternTextCall.found_in(module):
            yield CodeRuleViolation(
                path,
                occurrence.location.start.line,
                occurrence.location.end.line,
                "a pattern written as regular expression text; build it from "
                "named parts with basstler.regular_expression",
            )
