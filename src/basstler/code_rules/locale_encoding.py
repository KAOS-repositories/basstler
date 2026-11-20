"""
Finds text read or written in the locale encoding, which on Windows is a code page that
cannot encode most of Unicode.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import override

import libcst

from basstler.code_rules.checker import CodeRuleChecker, CodeRuleViolation
from basstler.code_rules.source_module import SourceModule

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


# %% the check


@dataclass(frozen=True)
class LocaleEncodingChecker(CodeRuleChecker):
    """
    Finds calls reading or writing text without naming its encoding: file reads and
    writes, files opened in text mode, and :mod:`subprocess` calls decoding their output.
    """

    @override
    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        module = SourceModule(path)
        for call in module.calls():
            if not self.uses_locale_encoding(module, call):
                continue
            yield CodeRuleViolation(
                path,
                module.first_line(call),
                module.last_line(call),
                "reads or writes text in the locale encoding, which on Windows cannot "
                f'encode most of Unicode; pass {TextKeyword.ENCODING}="utf-8"',
            )

    def uses_locale_encoding(self, module: SourceModule, call: libcst.Call) -> bool:
        """
        :return: Whether *call* reads or writes text without naming its encoding.
        """
        keywords = {
            argument.keyword.value: argument.value
            for argument in call.args
            if argument.keyword is not None
        }
        if TextKeyword.ENCODING in keywords:
            return False
        if module.refers_to(call.func, subprocess.__name__):
            switch = keywords.get(TextKeyword.TEXT)
            return isinstance(switch, libcst.Name) and switch.value == "True"
        function = call.func
        if isinstance(function, libcst.Attribute):
            name = function.attr.value
        elif isinstance(function, libcst.Name):
            name = function.value
        else:
            return False
        if name == TextFunction.OPEN:
            return self.opens_a_file(call) and not self.opens_bytes(call, keywords)
        return name in (TextFunction.READ_TEXT, TextFunction.WRITE_TEXT)

    @staticmethod
    def positional_arguments(call: libcst.Call) -> list[libcst.BaseExpression]:
        """
        :return: The arguments of *call* given by position.
        """
        return [argument.value for argument in call.args if argument.keyword is None]

    def opens_a_file(self, call: libcst.Call) -> bool:
        """
        :return: Whether *call*, an :data:`TextFunction.OPEN`, opens a file: a call of
            :func:`open`, or a method call given nothing but a mode, as
            :meth:`pathlib.Path.open` is, unlike an opener handed a request.
        """
        if isinstance(call.func, libcst.Name):
            return True
        return all(
            isinstance(argument, libcst.SimpleString | libcst.BaseNumber)
            for argument in self.positional_arguments(call)
        )

    def opens_bytes(
        self, call: libcst.Call, keywords: dict[str, libcst.BaseExpression]
    ) -> bool:
        """
        :param keywords: The keyword arguments of *call*, by name.
        :return: Whether *call*, an :data:`TextFunction.OPEN`, names a binary mode: by
            keyword, as the second argument of :func:`open` or the first of
            :meth:`pathlib.Path.open`.
        """
        mode_position = 0 if isinstance(call.func, libcst.Attribute) else 1
        mode = keywords.get(TextKeyword.MODE)
        positional = self.positional_arguments(call)
        if mode is None and len(positional) > mode_position:
            mode = positional[mode_position]
        return (
            isinstance(mode, libcst.SimpleString)
            and isinstance(mode.evaluated_value, str)
            and BINARY_MODE in mode.evaluated_value
        )
