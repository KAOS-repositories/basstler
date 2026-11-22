"""
Tests for :mod:`basstler.code_rules.locale_encoding`: reporting text read or written in
the locale encoding, which on Windows cannot encode most of Unicode.
"""

from __future__ import annotations

from basstler.code_rules.checker import CodeRulesCheck
from basstler.code_rules.locale_encoding import LocaleEncodingChecker
from basstler_testing.constants.paths import LocaleEncodingSnippet

from .marked_snippet import MarkedSnippet

# %% text


def test_every_kind_of_text_in_the_locale_encoding_is_reported():
    """
    File reads, writes and text-mode opens, and :mod:`subprocess` calls decoding their
    output, are each reported.
    """
    snippet = MarkedSnippet(LocaleEncodingSnippet.LOCALE_TEXT)
    assert snippet.reported_lines(LocaleEncodingChecker()) == snippet.marked_lines


def test_a_subprocess_imported_under_another_name_is_resolved():
    """
    A call is a :mod:`subprocess` call by what it imports, not by how it is spelled.
    """
    snippet = MarkedSnippet(LocaleEncodingSnippet.IMPORTED_SUBPROCESS)
    assert snippet.reported_lines(LocaleEncodingChecker()) == snippet.marked_lines


def test_text_as_utf_8_and_bytes_are_not_reported():
    """
    Calls naming their encoding, and calls handling bytes, are left alone.
    """
    snippet = MarkedSnippet(LocaleEncodingSnippet.UTF_8_TEXT)
    assert snippet.reported_lines(LocaleEncodingChecker()) == snippet.marked_lines


# %% calls that are not of open


def test_a_call_that_is_not_of_open_opens_no_file():
    """
    Only a call of :data:`TextFunction.OPEN` opens a file, whatever it is given.
    """
    assert (
        list(LocaleEncodingChecker().violations(LocaleEncodingSnippet.OTHER_CALLS))
        == []
    )


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
