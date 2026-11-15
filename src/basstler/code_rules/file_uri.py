"""
Finds file URLs built by putting a path after ``file://``, which on Windows gives no valid
URL, and fixes them to :meth:`pathlib.PurePath.as_uri`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import PurePath
from typing import override

import libcst

from basstler.class_property import classproperty
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.specification import Specification
from basstler.code_rules.fixes import (
    BehaviourDeclaration,
    BehaviourEffect,
    CodeFix,
    FixableChecker,
)

FILE_SCHEME = "file://"
"""
The text a file URL starts with.
"""

# %% the places


@dataclass(frozen=True)
class PathAfterFileScheme(Specification):
    """
    A formatted string that is :data:`FILE_SCHEME` followed by nothing but one path.
    """

    node: libcst.FormattedString
    """
    The formatted string.
    """

    path: libcst.BaseExpression
    """
    The expression giving the path.
    """


# %% the fix


class AsUriFix(CodeFix[PathAfterFileScheme]):
    """
    Replaces the formatted string with a call of :meth:`pathlib.PurePath.as_uri` on its
    path, parenthesised where the path is no primary expression.
    """

    @classproperty
    def behaviour(cls) -> BehaviourDeclaration:
        return BehaviourDeclaration(
            BehaviourEffect.CHANGED,
            "The URL percent-encodes characters such as spaces, writes a Windows path "
            "as file:///C:/..., and raises ValueError for a relative path; the "
            "interpolated value must be a path, not a string.",
        )

    def replacement(self, specification: PathAfterFileScheme) -> libcst.CSTNode:
        path = specification.path
        is_primary = isinstance(
            path, libcst.Name | libcst.Attribute | libcst.Call | libcst.Subscript
        )
        if not is_primary and not path.lpar:
            path = path.with_changes(
                lpar=[libcst.LeftParen()], rpar=[libcst.RightParen()]
            )
        return libcst.Call(
            libcst.Attribute(path, libcst.Name(PurePath.as_uri.__name__))
        )


# %% the check


@dataclass(frozen=True)
class FileUriChecker(FixableChecker[PathAfterFileScheme]):
    """
    Finds formatted strings that put one path after :data:`FILE_SCHEME`, leaving out
    those concatenated with another literal, where no call can take their place.
    """

    @classproperty
    def fix(cls) -> CodeFix[PathAfterFileScheme]:
        return AsUriFix()

    @classproperty
    def violation_description(cls) -> str:
        return (
            f"builds a file URL by putting a path after {FILE_SCHEME}, which gives no "
            f"valid URL for a Windows path; call {PurePath.as_uri.__name__}() on the "
            "path"
        )

    @override
    def specifications(self, module: PositionedModule) -> Iterator[PathAfterFileScheme]:
        concatenated = {
            part
            for node in module.positions
            if isinstance(node, libcst.ConcatenatedString)
            for part in (node.left, node.right)
        }
        for node, location in module.positions.items():
            if not isinstance(node, libcst.FormattedString) or node in concatenated:
                continue
            path = self.path_after_scheme(node)
            if path is not None:
                yield PathAfterFileScheme(location, node, path)

    @staticmethod
    def path_after_scheme(
        formatted: libcst.FormattedString,
    ) -> libcst.BaseExpression | None:
        """
        :return: The expression *formatted* puts after :data:`FILE_SCHEME`, ``None``
            unless that expression, unconverted and unformatted, is all that follows.
        """
        if len(formatted.parts) != 2:
            return None
        scheme, replacement = formatted.parts
        if not isinstance(scheme, libcst.FormattedStringText) or scheme.value != (
            FILE_SCHEME
        ):
            return None
        if not isinstance(replacement, libcst.FormattedStringExpression):
            return None
        if (
            replacement.conversion is not None
            or replacement.format_spec is not None
            or replacement.equal is not None
        ):
            return None
        return replacement.expression
