"""
Tests for :mod:`basstler.code_rules.pattern_building`: finding patterns written as
regular expression text.
"""

from __future__ import annotations

from basstler.code_rules.pattern_building import HandWrittenPatternChecker
from basstler.locations import PackageLocation

from ..constants.paths import PatternSnippet

# %% finding them


def reported_lines(path) -> list[int]:
    """
    :return: The first line of each hand-written pattern in *path*.
    """
    return [
        violation.first_line
        for violation in HandWrittenPatternChecker().violations(path)
    ]


def test_a_pattern_written_as_text_is_reported():
    """
    Both a call off ``re`` and an import of one of its pattern functions are reported.
    """
    imported_by_name_line, compiled_line = 8, 10
    assert reported_lines(PatternSnippet.HAND_WRITTEN) == [
        imported_by_name_line,
        compiled_line,
    ]


def test_a_pattern_built_from_named_parts_is_not_reported():
    """
    Building from named parts, and annotating with ``re``'s types, is the rule's own
    way.
    """
    assert reported_lines(PatternSnippet.FROM_NAMED_PARTS) == []


def test_the_module_building_the_patterns_is_not_reported():
    """
    The one module that turns named parts into pattern text compiles them.
    """
    assert reported_lines(PackageLocation.REGULAR_EXPRESSION_MODULE) == []


def test_the_program_importing_nothing_of_the_package_is_not_reported():
    """
    The helper's program cannot import the parts, and compiles a pattern the package
    built.
    """
    assert reported_lines(PackageLocation.UPSTREAM_REVIEWS_FETCH_PROGRAM) == []
