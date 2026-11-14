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

from basstler.class_property import classproperty
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.specification import Specification
from basstler.code_rules.fixes import (
    BehaviourDeclaration,
    BehaviourEffect,
    CodeFix,
    FixableChecker,
)

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

UTF_8 = "utf-8"
"""
The encoding every text is read and written in.
"""

CONSTANT_NAMES = frozenset({"True", "False", "None"})
"""
The names that are constants rather than variables.
"""


# %% the places


@dataclass(frozen=True)
class LocaleTextCall(Specification):
    """
    A call reading or writing text without naming its encoding.
    """

    node: libcst.Call
    """
    The call.
    """

    text_switch: libcst.Arg | None = None
    """
    The ``text=True`` argument by which a :mod:`subprocess` call decodes its output,
    which the encoding replaces.
    """


# %% the fix


class UTF8EncodingFix(CodeFix[LocaleTextCall]):
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

    def replacement(self, specification: LocaleTextCall) -> libcst.CSTNode:
        call = specification.node
        encoding = libcst.Arg(
            libcst.SimpleString(f'"{UTF_8}"'),
            keyword=libcst.Name(TextKeyword.ENCODING),
            equal=libcst.AssignEqual(
                whitespace_before=libcst.SimpleWhitespace(""),
                whitespace_after=libcst.SimpleWhitespace(""),
            ),
        )
        if specification.text_switch is not None:
            return call.deep_replace(
                specification.text_switch,
                specification.text_switch.with_changes(
                    keyword=encoding.keyword, value=encoding.value
                ),
            )
        if not call.args or not isinstance(call.args[-1].comma, libcst.Comma):
            return call.with_changes(args=[*call.args, encoding])
        last = call.args[-1]
        whitespace_before_last = (
            call.args[-2].comma.whitespace_after
            if len(call.args) > 1
            else call.whitespace_before_args
        )
        return call.with_changes(
            args=[
                *call.args[:-1],
                last.with_changes(
                    comma=last.comma.with_changes(
                        whitespace_after=whitespace_before_last
                    )
                ),
                encoding.with_changes(comma=last.comma),
            ]
        )


# %% the check


@dataclass(frozen=True)
class LocaleEncodingChecker(FixableChecker[LocaleTextCall]):
    """
    Finds calls reading or writing text without naming its encoding: file reads and
    writes, files opened in text mode, and :mod:`subprocess` calls decoding their output.
    """

    @classproperty
    def fix(cls) -> CodeFix[LocaleTextCall]:
        return UTF8EncodingFix()

    @classproperty
    def violation_description(cls) -> str:
        return (
            "reads or writes text in the locale encoding, which on Windows cannot "
            f'encode most of Unicode; pass {TextKeyword.ENCODING}="{UTF_8}"'
        )

    @override
    def specifications(self, module: PositionedModule) -> Iterator[LocaleTextCall]:
        for node, location in module.positions.items():
            if not isinstance(node, libcst.Call):
                continue
            specification = self.locale_text_call(node, location)
            if specification is not None:
                yield specification

    def locale_text_call(
        self, call: libcst.Call, location: libcst.metadata.CodeRange
    ) -> LocaleTextCall | None:
        """
        :param location: The code range of *call*.
        :return: *call* as a place breaking the rule, ``None`` when it names its
            encoding or handles no text.
        """
        keywords = {
            argument.keyword.value: argument
            for argument in call.args
            if argument.keyword is not None
        }
        if TextKeyword.ENCODING in keywords:
            return None
        if self.is_subprocess_call(call):
            switch = keywords.get(TextKeyword.TEXT)
            if switch is None or not self.is_name(switch.value, "True"):
                return None
            return LocaleTextCall(location, call, switch)
        function = call.func
        name = function.attr.value if isinstance(function, libcst.Attribute) else None
        if isinstance(function, libcst.Name):
            name = function.value
        if name == TextFunction.OPEN:
            if not self.opens_a_file(call) or self.opens_bytes(call, keywords):
                return None
            return LocaleTextCall(location, call)
        if name in (TextFunction.READ_TEXT, TextFunction.WRITE_TEXT):
            return LocaleTextCall(location, call)
        return None

    @staticmethod
    def is_name(expression: libcst.BaseExpression, name: str) -> bool:
        """
        :return: Whether *expression* is the bare name *name*.
        """
        return isinstance(expression, libcst.Name) and expression.value == name

    def is_subprocess_call(self, call: libcst.Call) -> bool:
        """
        :return: Whether *call* calls a function of :mod:`subprocess`.
        """
        function = call.func
        return isinstance(function, libcst.Attribute) and self.is_name(
            function.value, subprocess.__name__
        )

    @staticmethod
    def positional_arguments(call: libcst.Call) -> list[libcst.Arg]:
        """
        :return: The arguments *call* passes by position, ``*`` unpackings included.
        """
        return [
            argument
            for argument in call.args
            if argument.keyword is None and argument.star != "**"
        ]

    def opens_a_file(self, call: libcst.Call) -> bool:
        """
        :return: Whether *call*, an :data:`TextFunction.OPEN`, opens a file: a call of
            :func:`open`, or a method call given nothing but constants, as
            :meth:`pathlib.Path.open` is, unlike an opener handed a request.
        """
        if isinstance(call.func, libcst.Name):
            return True
        return all(
            argument.star == "" and self.is_constant(argument.value)
            for argument in self.positional_arguments(call)
        )

    @staticmethod
    def is_constant(expression: libcst.BaseExpression) -> bool:
        """
        :return: Whether *expression* is a literal number, string, bytes, ellipsis or
            one of :data:`CONSTANT_NAMES`.
        """
        if isinstance(expression, libcst.Name):
            return expression.value in CONSTANT_NAMES
        if isinstance(expression, libcst.ConcatenatedString):
            return expression.evaluated_value is not None
        return isinstance(
            expression,
            libcst.SimpleString
            | libcst.Integer
            | libcst.Float
            | libcst.Imaginary
            | libcst.Ellipsis,
        )

    def opens_bytes(self, call: libcst.Call, keywords: dict[str, libcst.Arg]) -> bool:
        """
        :param keywords: The keyword arguments of *call*, by name.
        :return: Whether *call*, an :data:`TextFunction.OPEN`, names a binary mode: by
            keyword, as the second argument of :func:`open` or the first of
            :meth:`pathlib.Path.open`.
        """
        mode_position = 0 if isinstance(call.func, libcst.Attribute) else 1
        positional = self.positional_arguments(call)
        mode = (
            keywords[TextKeyword.MODE].value if TextKeyword.MODE in keywords else None
        )
        if mode is None and len(positional) > mode_position:
            mode = positional[mode_position].value
        if not isinstance(mode, libcst.SimpleString | libcst.ConcatenatedString):
            return False
        value = mode.evaluated_value
        return isinstance(value, str) and BINARY_MODE in value
