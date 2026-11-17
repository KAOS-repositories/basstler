"""
Tests for :mod:`basstler.code_rules.text_file_usage`: reporting the text a path reads and
writes itself, which a text file reads and writes as UTF-8.
"""

from __future__ import annotations

from basstler.code_rules.text_file_usage import TextFileChecker

from ..constants.paths import TextFileUsageSnippet

# %% what is reported


def test_every_read_and_write_of_a_path_is_reported():
    """
    A path's text read and written as UTF-8 or in the locale encoding is reported.
    """
    violations = TextFileChecker().violations(TextFileUsageSnippet.PATH_TEXT_CALLS)
    assert [violation.first_line for violation in violations] == list(range(10, 14))


def test_what_a_text_file_does_not_do_is_not_reported():
    """
    Another encoding, error handling, newline translation and bytes are left alone.
    """
    assert list(TextFileChecker().violations(TextFileUsageSnippet.KEPT_CALLS)) == []
