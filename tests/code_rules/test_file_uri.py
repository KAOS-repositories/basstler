"""
Tests for :mod:`basstler.code_rules.file_uri`: reporting file URLs built by putting a
path after ``file://``.
"""

from __future__ import annotations

from basstler.code_rules.checker import CodeRulesCheck
from basstler.code_rules.file_uri import FileUriChecker

from ..constants.paths import FileUriSnippet

# %% file URLs


def test_a_path_put_after_the_file_scheme_is_reported():
    """
    Each formatted string that is ``file://`` followed by one path is reported.
    """
    violations = FileUriChecker().violations(FileUriSnippet.PATH_AFTER_SCHEME)
    assert [violation.first_line for violation in violations] == [10, 11]


def test_other_urls_are_not_reported():
    """
    URLs that are anything but ``file://`` and one unconverted path are left alone.
    """
    assert list(FileUriChecker().violations(FileUriSnippet.OTHER_URLS)) == []


# %% this repository


def test_no_code_in_the_repository_puts_a_path_after_the_file_scheme(
    repository_sources,
):
    """
    Every file URL the package, its scripts and its suite build comes from
    :meth:`pathlib.PurePath.as_uri`, which Windows paths need.
    """
    violations = CodeRulesCheck((FileUriChecker(),)).violations(repository_sources)
    assert [violation.render() for violation in violations] == []
