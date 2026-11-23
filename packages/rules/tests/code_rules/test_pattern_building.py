"""
Tests for :mod:`basstler.code_rules.pattern_building`: finding patterns written as
regular expression text.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.code_rules.pattern_building import HandWrittenPatternChecker
from basstler.locations import PackageLocation
from basstler.text_file import TextFile

from basstler_testing.constants.paths import PatternSnippet

# %% finding them


def reported_code(path: Path) -> list[str]:
    """
    :return: The source text of each line in *path* the checker reports, so a result
        reads as the code it found.
    """
    lines = TextFile(path).read().splitlines()
    return [
        lines[violation.first_line - 1].strip()
        for violation in HandWrittenPatternChecker().violations(path)
    ]


@pytest.mark.parametrize(
    ("snippet", "reported"),
    [
        (
            PatternSnippet.HAND_WRITTEN,
            ['DIGITS = re.compile(r"\\d+")', 'return findall(r"\\w+", text)'],
        ),
        (
            PatternSnippet.ALIASED_MODULE,
            ['return regular_expressions.search(r"[0-9]+", text)'],
        ),
        (PatternSnippet.ALIASED_FUNCTION, ['WORDS = build_pattern(r"\\w+")']),
        (PatternSnippet.FROM_NAMED_PARTS, []),
        (PatternSnippet.SAME_NAMES, []),
    ],
    ids=[
        "pattern text through re and through a function imported from it",
        "pattern text through the module under another name",
        "pattern text through a function under another name",
        "a pattern built from named parts",
        "functions that only share a name, and the builtin compile",
    ],
)
def test_a_pattern_written_as_text_is_reported_however_re_is_imported(
    snippet: Path, reported: list[str]
):
    """
    Each snippet is listed beside the code of it the checker reports.
    """
    assert reported_code(snippet) == reported


@pytest.mark.parametrize(
    ("allowed_module", "why"),
    [
        (PackageLocation.REGULAR_EXPRESSION_MODULE, "it turns named parts into text"),
        (
            PackageLocation.UPSTREAM_REVIEWS_FETCH,
            "it can import nothing of the package",
        ),
    ],
)
def test_the_modules_that_must_compile_pattern_text_are_not_reported(
    allowed_module: Path, why: str
):
    """
    The module building every pattern, and the helper program that compiles a pattern
    the package built, are the rule's two exemptions.
    """
    assert reported_code(allowed_module) == [], why
