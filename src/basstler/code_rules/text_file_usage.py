"""
Finds the text a path reads and writes itself, which a text file reads and writes as
UTF-8.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import override

import libcst
from libcst import matchers

from basstler.class_property import classproperty
from basstler.code_modification.patterns import CodePattern
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.specification import Specification
from basstler.code_modification.syntax import ExpressionSyntax
from basstler.code_rules.fixes import (
    BehaviourDeclaration,
    BehaviourEffect,
    CodeFix,
    FixableChecker,
)
from basstler.code_rules.locale_encoding import TextFunction, TextKeyword
from basstler.locations import PackageLocation
from basstler.text_file import UTF_8, TextFile

# %% the fix


class TextFileFix(CodeFix[Specification]):
    """
    Reads and writes through a :class:`~basstler.text_file.TextFile` of the path.
    """

    @classproperty
    def behaviour(cls) -> BehaviourDeclaration:
        return BehaviourDeclaration(
            BehaviourEffect.CHANGED,
            "Text is read and written as UTF-8 instead of in the locale encoding; "
            "nothing changes where the locale encoding is UTF-8.",
        )

    def required_imports(self, specification: Specification) -> tuple[type, ...]:
        return (TextFile,)

    def replacement(self, specification: Specification) -> libcst.Call:
        call = libcst.ensure_type(specification.node, libcst.Call)
        path_method = libcst.ensure_type(call.func, libcst.Attribute)
        text_file = libcst.Call(
            libcst.Name(TextFile.__name__), [libcst.Arg(path_method.value)]
        )
        method = (
            TextFile.read
            if path_method.attr.value == TextFunction.READ_TEXT
            else TextFile.write
        )
        text = [libcst.Arg(argument.value) for argument in call.args[:1]]
        return libcst.Call(
            libcst.Attribute(text_file, libcst.Name(method.__name__)),
            text if method is TextFile.write else [],
        )


# %% the pattern


class UTF8EncodingArgument(CodePattern):
    """
    The argument that names UTF-8 as the encoding.
    """

    @classproperty
    def matcher(cls) -> matchers.Arg:
        return matchers.Arg(
            keyword=matchers.Name(TextKeyword.ENCODING),
            value=matchers.MatchIfTrue(
                lambda value: ExpressionSyntax(value).literal_text == UTF_8
            ),
        )


class TextFileCall(CodePattern):
    """
    A read, or a write of one text, of a path, with no encoding or UTF-8 and nothing
    else a text file lacks.
    """

    @classproperty
    def matcher(cls) -> matchers.OneOf:
        encoding = matchers.ZeroOrOne(UTF8EncodingArgument.matcher)
        return matchers.OneOf(
            matchers.Call(
                func=matchers.Attribute(attr=matchers.Name(TextFunction.READ_TEXT)),
                args=[encoding],
            ),
            matchers.Call(
                func=matchers.Attribute(attr=matchers.Name(TextFunction.WRITE_TEXT)),
                args=[matchers.Arg(keyword=None, star=""), encoding],
            ),
        )


# %% the check


@dataclass(frozen=True)
class TextFileChecker(FixableChecker[Specification]):
    """
    Finds calls of a path's ``read_text`` and ``write_text`` that name no encoding or
    UTF-8 and pass nothing else a text file lacks.
    """

    @classproperty
    def fix(cls) -> CodeFix[Specification]:
        return TextFileFix()

    @classproperty
    def violation_description(cls) -> str:
        return (
            f"reads or writes text through the path; use "
            f'{TextFile.__name__} for {TextKeyword.ENCODING}="{UTF_8}"'
        )

    @override
    def checks(self, path: Path) -> bool:
        """
        Skips the program that runs without ``basstler``; :meth:`FixableChecker.checks`.
        """
        return path.resolve() != PackageLocation.UPSTREAM_REVIEWS_FETCH.resolve()

    @override
    def specifications_of_module(
        self, module: PositionedModule
    ) -> Iterator[Specification]:
        for occurrence in TextFileCall.found_in(module):
            yield Specification(occurrence.location, occurrence.node)
