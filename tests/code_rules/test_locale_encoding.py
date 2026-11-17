"""
Tests for :mod:`basstler.code_rules.locale_encoding`: reporting text read or written in
the locale encoding, which on Windows cannot encode most of Unicode.
"""

from __future__ import annotations

import libcst.matchers as matchers

from basstler.code_modification.source_file import PythonSourceFile
from basstler.code_modification.syntax import CallSyntax
from basstler.code_rules.checker import CodeRulesCheck
from basstler.code_rules.locale_encoding import LocaleEncodingChecker

from ..constants.paths import LocaleEncodingSnippet

# %% text


def test_every_kind_of_text_in_the_locale_encoding_is_reported():
    """
    File reads, writes and text-mode opens, and :mod:`subprocess` calls decoding their
    output, are each reported.
    """
    violations = LocaleEncodingChecker().violations(LocaleEncodingSnippet.LOCALE_TEXT)
    assert [violation.first_line for violation in violations] == list(range(12, 17))


def test_text_as_utf_8_and_bytes_are_not_reported():
    """
    Calls naming their encoding, and calls handling bytes, are left alone.
    """
    assert (
        list(LocaleEncodingChecker().violations(LocaleEncodingSnippet.UTF_8_TEXT)) == []
    )


# %% calls that are not of open


def other_calls() -> list[CallSyntax]:
    """
    :return: The calls of the snippet of calls that are not of :func:`open`.
    """
    module = PythonSourceFile(LocaleEncodingSnippet.OTHER_CALLS).parse()
    return [CallSyntax(node) for node in matchers.findall(module, matchers.Call())]


def test_a_call_that_is_not_of_open_opens_no_file():
    """
    Only a call of :data:`TextFunction.OPEN` opens a file, whatever it is given.
    """
    assert [LocaleEncodingChecker.opens_a_file(call) for call in other_calls()] == [
        False,
        False,
    ]


def test_a_call_that_is_not_of_open_names_no_binary_mode():
    """
    Only a call of :data:`TextFunction.OPEN` has a mode, whatever it is given.
    """
    assert [LocaleEncodingChecker.opens_bytes(call) for call in other_calls()] == [
        False,
        False,
    ]


# %% this repository


def test_no_code_in_the_repository_reads_or_writes_text_in_the_locale_encoding(
    repository_sources,
):
    """
    Every text the package, its scripts and its suite read or write is UTF-8, so the
    suite passes on Windows too.
    """
    violations = CodeRulesCheck((LocaleEncodingChecker(),)).violations(
        repository_sources
    )
    assert [violation.render() for violation in violations] == []
