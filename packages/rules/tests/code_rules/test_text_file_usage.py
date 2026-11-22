"""
Tests for :mod:`basstler.code_rules.text_file_usage`: reporting the text a path reads and
writes itself, which a text file reads and writes as UTF-8.
"""

from __future__ import annotations

from basstler.code_rules.text_file_usage import TextFileChecker
from basstler.locations import PackageLocation

from basstler_testing.constants.paths import TextFileUsageSnippet

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


def test_the_program_that_runs_without_basstler_is_not_checked():
    """
    The program a helper session runs imports nothing of the package, so it is skipped.
    """
    checker = TextFileChecker()

    assert not checker.checks(PackageLocation.UPSTREAM_REVIEWS_FETCH)
    assert checker.checks(TextFileUsageSnippet.PATH_TEXT_CALLS)
