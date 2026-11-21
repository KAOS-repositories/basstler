"""
Tests for :mod:`basstler.code_rules.posix_path_text`: reporting paths turned into text
that separates their parts with ``\\`` on Windows.
"""

from __future__ import annotations

from basstler.code_rules.checker import CodeRulesCheck
from basstler.code_rules.posix_path_text import PosixPathTextChecker

from ..constants.paths import PosixPathTextSnippet

# %% text that is no path


def test_text_that_is_no_known_path_is_not_reported():
    """
    Text of no path, of a path whose type the module does not show, and POSIX text are
    left alone.
    """
    assert (
        list(PosixPathTextChecker().violations(PosixPathTextSnippet.OTHER_TEXT)) == []
    )


# %% this repository


def test_no_code_in_the_repository_turns_a_known_path_into_other_text(
    repository_sources,
):
    """
    Every path the package, its scripts and its suite turn into text is POSIX text,
    which reads the same on Windows.
    """
    violations = CodeRulesCheck((PosixPathTextChecker(),)).violations(
        repository_sources
    )
    assert [violation.render() for violation in violations] == []
