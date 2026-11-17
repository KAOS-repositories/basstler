"""
Finds the text a path reads and writes itself, which a text file reads and writes as
UTF-8.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import override

import libcst

from basstler.class_property import classproperty
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.specification import Specification
from basstler.code_modification.syntax import CallSyntax, ExpressionSyntax
from basstler.code_rules.fixes import (
    BehaviourDeclaration,
    BehaviourEffect,
    CodeFix,
    FixableChecker,
)
from basstler.code_rules.locale_encoding import TextFunction, TextKeyword
from basstler.text_file import UTF_8, TextFile

# %% the fix


class TextFileMethod(StrEnum):
    """
    The methods of a text file, by the path method each stands for.
    """

    READ = "read"
    """
    :meth:`basstler.text_file.TextFile.read`.
    """

    WRITE = "write"
    """
    :meth:`basstler.text_file.TextFile.write`.
    """


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

    @classproperty
    def required_import(cls) -> libcst.SimpleStatementLine:
        return libcst.parse_statement(
            f"from {TextFile.__module__} import {TextFile.__name__}\n"
        )

    def replacement(self, specification: Specification) -> libcst.Call:
        call = libcst.ensure_type(specification.node, libcst.Call)
        path_method = libcst.ensure_type(call.func, libcst.Attribute)
        text_file = libcst.Call(
            libcst.Name(TextFile.__name__), [libcst.Arg(path_method.value)]
        )
        method = (
            TextFileMethod.READ
            if path_method.attr.value == TextFunction.READ_TEXT
            else TextFileMethod.WRITE
        )
        text = [libcst.Arg(argument.value) for argument in call.args[:1]]
        return libcst.Call(
            libcst.Attribute(text_file, libcst.Name(method)),
            text if method is TextFileMethod.WRITE else [],
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
    def specifications_of_module(
        self, module: PositionedModule
    ) -> Iterator[Specification]:
        for node, location in module.positions.items():
            if isinstance(node, libcst.Call) and self.is_text_call(CallSyntax(node)):
                yield Specification(location, node)

    @staticmethod
    def is_text_call(call: CallSyntax) -> bool:
        """
        :return: Whether *call* is a call of a path's ``read_text`` or ``write_text``
            that a :class:`~basstler.text_file.TextFile` makes in the same way.
        """
        if not isinstance(call.call.func, libcst.Attribute):
            return False
        name = ExpressionSyntax(call.call.func).final_name
        if name not in (TextFunction.READ_TEXT, TextFunction.WRITE_TEXT):
            return False
        texts = 0 if name == TextFunction.READ_TEXT else 1
        keywords = call.keyword_arguments
        if len(call.call.args) != len(call.positional_arguments) + len(keywords):
            return False
        encoding = keywords.get(TextKeyword.ENCODING)
        if len(call.positional_arguments) != texts or set(keywords) - {
            TextKeyword.ENCODING
        }:
            return False
        return (
            encoding is None or ExpressionSyntax(encoding.value).literal_text == UTF_8
        )
