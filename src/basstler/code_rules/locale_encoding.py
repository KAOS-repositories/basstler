"""
Finds text read or written in the locale encoding, which on Windows is a code page that
cannot encode most of Unicode, and fixes it to UTF-8.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import override

import libcst
from libcst.metadata import CodeRange

from basstler.class_property import classproperty
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.syntax import CallSyntax, ConstantName, ExpressionSyntax
from basstler.code_rules.fixes import (
    BehaviourDeclaration,
    BehaviourEffect,
    CallLackingKeywordArgument,
    CodeFix,
    FixableChecker,
    KeywordArgumentFix,
)
from basstler.text_file import UTF_8

# %% what reads and writes text


class TextFunction(StrEnum):
    """
    The functions and methods that read or write text in the locale encoding unless
    given one.
    """

    READ_TEXT = "read_text"
    """
    :meth:`pathlib.Path.read_text`.
    """

    WRITE_TEXT = "write_text"
    """
    :meth:`pathlib.Path.write_text`.
    """

    OPEN = "open"
    """
    :func:`open` and :meth:`pathlib.Path.open`, unless they open the file in binary
    mode.
    """


class TextKeyword(StrEnum):
    """
    The keyword arguments that decide how a call reads and writes text.
    """

    ENCODING = "encoding"
    """
    The encoding text is read and written in.
    """

    MODE = "mode"
    """
    The mode :data:`TextFunction.OPEN` opens a file in.
    """

    TEXT = "text"
    """
    The :mod:`subprocess` switch decoding output in the locale encoding.
    """


BINARY_MODE = "b"
"""
The letter in a file mode that opens the file for bytes rather than text.
"""


# %% the fix


class UTF8EncodingFix(KeywordArgumentFix):
    """
    Names UTF-8 as the encoding, in place of the :mod:`subprocess` text switch where the
    call has one.
    """

    @classproperty
    def behaviour(cls) -> BehaviourDeclaration:
        return BehaviourDeclaration(
            BehaviourEffect.CHANGED,
            "Text is read and written as UTF-8 instead of in the locale encoding; "
            "nothing changes where the locale encoding is UTF-8.",
        )

    @classproperty
    def keyword(cls) -> str:
        return TextKeyword.ENCODING

    @classproperty
    def value(cls) -> libcst.BaseExpression:
        return libcst.SimpleString(f'"{UTF_8}"')


# %% the check


@dataclass(frozen=True)
class LocaleEncodingChecker(FixableChecker[CallLackingKeywordArgument]):
    """
    Finds calls reading or writing text without naming its encoding: file reads and
    writes, files opened in text mode, and :mod:`subprocess` calls decoding their output.
    """

    @classproperty
    def fix(cls) -> CodeFix[CallLackingKeywordArgument]:
        return UTF8EncodingFix()

    @classproperty
    def violation_description(cls) -> str:
        return (
            "reads or writes text in the locale encoding, which on Windows cannot "
            f'encode most of Unicode; pass {TextKeyword.ENCODING}="{UTF_8}"'
        )

    @override
    def specifications_of_module(
        self, module: PositionedModule
    ) -> Iterator[CallLackingKeywordArgument]:
        for node, location in module.positions.items():
            if not isinstance(node, libcst.Call):
                continue
            specification = self.locale_text_call(CallSyntax(node), location)
            if specification is not None:
                yield specification

    def locale_text_call(
        self, call: CallSyntax, location: CodeRange
    ) -> CallLackingKeywordArgument | None:
        """
        :param location: The code range of *call*.
        :return: *call* as a place breaking the rule, superseding its ``text=True`` where
            it is a :mod:`subprocess` call; ``None`` when it names its encoding or
            handles no text.
        """
        keywords = call.keyword_arguments
        if TextKeyword.ENCODING in keywords:
            return None
        if self.is_subprocess_call(call):
            switch = keywords.get(TextKeyword.TEXT)
            if switch is None or not ExpressionSyntax(switch.value).is_name(
                ConstantName.TRUE
            ):
                return None
            return CallLackingKeywordArgument(location, call.call, switch)
        name = ExpressionSyntax(call.call.func).final_name
        if name == TextFunction.OPEN:
            if not self.opens_a_file(call) or self.opens_bytes(call):
                return None
            return CallLackingKeywordArgument(location, call.call)
        if name in (TextFunction.READ_TEXT, TextFunction.WRITE_TEXT):
            return CallLackingKeywordArgument(location, call.call)
        return None

    @staticmethod
    def is_subprocess_call(call: CallSyntax) -> bool:
        """
        :return: Whether *call* calls a function of :mod:`subprocess`.
        """
        function = call.call.func
        return isinstance(function, libcst.Attribute) and ExpressionSyntax(
            function.value
        ).is_name(subprocess.__name__)

    @staticmethod
    def opens_a_file(call: CallSyntax) -> bool:
        """
        :return: Whether *call*, an :data:`TextFunction.OPEN`, opens a file: a call of
            :func:`open`, or a method call given nothing but constants, as
            :meth:`pathlib.Path.open` is, unlike an opener handed a request.
        """
        if isinstance(call.call.func, libcst.Name):
            return True
        return all(
            argument.star == "" and ExpressionSyntax(argument.value).is_constant
            for argument in call.positional_arguments
        )

    @staticmethod
    def opens_bytes(call: CallSyntax) -> bool:
        """
        :return: Whether *call*, an :data:`TextFunction.OPEN`, names a binary mode: by
            keyword, as the second argument of :func:`open` or the first of
            :meth:`pathlib.Path.open`.
        """
        mode_position = 0 if isinstance(call.call.func, libcst.Attribute) else 1
        positional = call.positional_arguments
        mode_argument = call.keyword_arguments.get(TextKeyword.MODE)
        if mode_argument is None and len(positional) > mode_position:
            mode_argument = positional[mode_position]
        if mode_argument is None:
            return False
        mode = ExpressionSyntax(mode_argument.value).literal_text
        return mode is not None and BINARY_MODE in mode
