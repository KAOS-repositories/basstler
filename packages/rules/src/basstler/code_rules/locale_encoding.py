"""
Finds text read or written in the locale encoding, which on Windows is a code page that
cannot encode most of Unicode, and fixes it to UTF-8.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import override

import libcst
from libcst import matchers

from basstler.class_property import classproperty
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.patterns import CodePattern
from basstler.code_modification.syntax import ConstantName, ExpressionSyntax
from basstler.code_rules.fixes import (
    BehaviourDeclaration,
    BehaviourEffect,
    CallLackingKeywordArgument,
    CodeFix,
    FixableChecker,
    KeywordArgumentFix,
)
from basstler.code_rules.subprocess_function import SubprocessFunction
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


# %% the patterns


class NonEncodingArgument(CodePattern):
    """
    An argument that is not the encoding.
    """

    @classproperty
    def matcher(cls) -> matchers.Arg:
        return matchers.Arg(
            keyword=matchers.DoesNotMatch(matchers.Name(TextKeyword.ENCODING))
        )


class ConstantPositionalArgument(CodePattern):
    """
    A positional argument given a constant, as :meth:`pathlib.Path.open` is.
    """

    @classproperty
    def matcher(cls) -> matchers.Arg:
        return matchers.Arg(
            keyword=None,
            star="",
            value=matchers.MatchIfTrue(
                lambda value: ExpressionSyntax(value).is_constant
            ),
        )


class SubprocessTextSwitch(CodePattern):
    """
    A call of a :mod:`subprocess` function that decodes its output in the locale
    encoding; the ``text=True`` argument is saved as :attr:`saved_switch_name`.
    """

    @classproperty
    def saved_switch_name(cls) -> str:
        """
        The name the ``text=True`` argument is saved under when the pattern matches.
        """
        return "switch"

    @classproperty
    def matcher(cls) -> matchers.Call:
        others = matchers.ZeroOrMore(NonEncodingArgument.matcher)
        switch = matchers.Arg(
            keyword=matchers.Name(TextKeyword.TEXT),
            value=matchers.Name(ConstantName.TRUE),
        )
        return matchers.Call(
            func=SubprocessFunction.matcher,
            args=[
                others,
                matchers.SaveMatchedNode(switch, cls.saved_switch_name),
                others,
            ],
        )


class BinaryModeArgument(CodePattern):
    """
    An argument that names a binary mode.
    """

    @classproperty
    def matcher(cls) -> matchers.Arg:
        return matchers.Arg(
            value=matchers.MatchIfTrue(
                lambda value: (
                    BINARY_MODE in (ExpressionSyntax(value).literal_text or "")
                )
            )
        )


class BinaryOpen(CodePattern):
    """
    A call of :func:`open` or :meth:`pathlib.Path.open` that names a binary mode: by
    keyword, as the second argument of the function or the first of the method.
    """

    @classproperty
    def matcher(cls) -> matchers.OneOf:
        binary = BinaryModeArgument.matcher
        by_keyword = matchers.Arg(
            keyword=matchers.Name(TextKeyword.MODE), value=binary.value
        )
        function = matchers.Name(TextFunction.OPEN)
        method = matchers.Attribute(attr=matchers.Name(TextFunction.OPEN))
        return matchers.OneOf(
            matchers.Call(
                func=matchers.OneOf(function, method),
                args=[matchers.ZeroOrMore(), by_keyword, matchers.ZeroOrMore()],
            ),
            matchers.Call(
                func=function,
                args=[matchers.Arg(keyword=None), binary, matchers.ZeroOrMore()],
            ),
            matchers.Call(func=method, args=[binary, matchers.ZeroOrMore()]),
        )


class FileOpen(CodePattern):
    """
    A call of :func:`open`, or of a method named so that is given nothing but constants
    as :meth:`pathlib.Path.open` is, unlike an opener handed a request; unless it names
    its encoding.
    """

    @classproperty
    def matcher(cls) -> matchers.OneOf:
        keyword = matchers.Arg(
            keyword=matchers.AllOf(
                matchers.Name(),
                matchers.DoesNotMatch(matchers.Name(TextKeyword.ENCODING)),
            )
        )
        unpacked_keywords = matchers.Arg(keyword=None, star="**")
        return matchers.OneOf(
            matchers.Call(
                func=matchers.Name(TextFunction.OPEN),
                args=[matchers.ZeroOrMore(NonEncodingArgument.matcher)],
            ),
            matchers.Call(
                func=matchers.Attribute(attr=matchers.Name(TextFunction.OPEN)),
                args=[
                    matchers.ZeroOrMore(
                        matchers.OneOf(
                            keyword,
                            ConstantPositionalArgument.matcher,
                            unpacked_keywords,
                        )
                    )
                ],
            ),
        )


class PathReadOrWrite(CodePattern):
    """
    A call of ``read_text`` or ``write_text`` that names no encoding.
    """

    @classproperty
    def matcher(cls) -> matchers.Call:
        text_function = matchers.OneOf(
            matchers.Name(TextFunction.READ_TEXT),
            matchers.Name(TextFunction.WRITE_TEXT),
        )
        return matchers.Call(
            func=matchers.OneOf(text_function, matchers.Attribute(attr=text_function)),
            args=[matchers.ZeroOrMore(NonEncodingArgument.matcher)],
        )


class LocaleTextCall(CodePattern):
    """
    A call that reads or writes text without naming its encoding.
    """

    @classproperty
    def matcher(cls) -> matchers.OneOf:
        return matchers.OneOf(
            SubprocessTextSwitch.matcher,
            FileOpen.matcher,
            PathReadOrWrite.matcher,
        )


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
        for occurrence in LocaleTextCall.found_in(module):
            call = libcst.ensure_type(occurrence.node, libcst.Call)
            if BinaryOpen.matches(call, module.metadata):
                continue
            captured = LocaleTextCall.captures(call, module.metadata)
            yield CallLackingKeywordArgument(
                occurrence.location,
                call,
                captured.get(SubprocessTextSwitch.saved_switch_name),
            )
