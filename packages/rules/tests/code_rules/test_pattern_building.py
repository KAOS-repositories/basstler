"""
Tests for :mod:`basstler.code_rules.pattern_building`: finding patterns written as
regular expression text.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.code_rules.pattern_building import HandWrittenPatternChecker
from basstler.locations import PackageLocation, ShippedPath
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


def copy_of_snippet_at(snippet: Path, destination: Path) -> Path:
    """
    :param snippet: A file with hand-written patterns.
    :param destination: Where to put a copy of it.
    :return: The copy, in a directory made for it.
    """
    destination.parent.mkdir(parents=True)
    TextFile(destination).write(TextFile(snippet).read())
    return destination


@pytest.mark.parametrize(
    ("exempt_module", "why"),
    [
        (ShippedPath.REGULAR_EXPRESSION_MODULE, "it turns named parts into text"),
        (ShippedPath.UPSTREAM_REVIEWS_FETCH, "it can import nothing of the package"),
    ],
)
def test_the_modules_that_must_compile_pattern_text_are_not_reported(
    exempt_module: ShippedPath, why: str, tmp_path: Path
):
    """
    The module building every pattern, and the helper program that compiles a pattern
    the package built, are the rule's two exemptions, wherever their distribution is
    installed.
    """
    exempt = copy_of_snippet_at(
        PatternSnippet.HAND_WRITTEN,
        tmp_path / PackageLocation.DIRECTORY.name / exempt_module,
    )

    assert reported_code(exempt) == [], why


def test_the_code_of_an_exempt_module_is_reported_in_any_other_file(tmp_path: Path):
    """
    The exemption belongs to the two modules, not to the code in them.
    """
    other = copy_of_snippet_at(
        PatternSnippet.HAND_WRITTEN,
        tmp_path / PackageLocation.DIRECTORY.name / "other.py",
    )

    assert reported_code(other) == reported_code(PatternSnippet.HAND_WRITTEN) != []
