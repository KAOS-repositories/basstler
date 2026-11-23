"""
Tests for the patterns the code rules read text with: a diff's headers, a section's
words, the comments and fields prose length skips, and an installed requirement.
"""

from __future__ import annotations

import pytest

from basstler.code_rules.checker import DiffHeaderGroup, StagedLines
from basstler.code_rules.package_boundaries import EXTRA_MARKER, InstalledLibraries
from basstler.code_rules.prose_length import SourceProse, ToolDirective
from basstler.code_rules.rule import Section

# %% a diff's headers


@pytest.mark.parametrize(
    ("line", "file", "first_line", "line_count"),
    [
        (
            "diff --git a/old/a.py b/packages/core/a.py",
            "packages/core/a.py",
            None,
            None,
        ),
        ("@@ -3 +7,4 @@", None, "7", "4"),
        ("@@ -3,2 +9 @@ def x():", None, "9", None),
        ("+++ b/packages/core/a.py", None, None, None),
        ("--- a/packages/core/a.py", None, None, None),
        ("diff --git a/old b/", None, None, None),
        ("@@ no ranges @@", None, None, None),
        ("a line of code", None, None, None),
    ],
)
def test_a_file_header_and_a_changed_block_header_are_read_from_a_diff(
    line: str, file: str | None, first_line: str | None, line_count: str | None
):
    """
    Each diff line is listed beside the file, first line and line count read from it.
    """
    found = StagedLines.diff_header.search(line)

    assert (
        (
            found[DiffHeaderGroup.STAGED_FILE],
            found[DiffHeaderGroup.FIRST_LINE],
            found[DiffHeaderGroup.LINE_COUNT],
        )
        if found
        else (None, None, None)
    ) == (file, first_line, line_count)


# %% a section's title


class QualityRules(Section):
    """
    A section named for one word.
    """


class CodeStyleRules(Section):
    """
    A section named for two words.
    """


class CIPipelineRules(Section):
    """
    A section whose name starts with an acronym.
    """


class HTTPSettingsRules(Section):
    """
    A section whose acronym is followed by a capitalised word.
    """


@pytest.mark.parametrize(
    ("section", "title"),
    [
        (QualityRules, "Quality"),
        (CodeStyleRules, "Code style"),
        (CIPipelineRules, "CI pipeline"),
        (HTTPSettingsRules, "HTTP settings"),
    ],
)
def test_a_section_is_titled_by_the_words_of_its_name(
    section: type[Section], title: str
):
    """
    Each section is listed beside its title.
    """
    assert section.title == title


# %% prose that is not counted


@pytest.mark.parametrize(
    ("line", "is_a_field"),
    [
        (":param name: what it is", True),
        (":return: the value", True),
        (":raises ValueError: when", True),
        ("::", False),
        (": spaced", False),
        ("prose :param inside:", False),
        ("", False),
    ],
)
def test_a_line_starting_a_field_list_is_an_rst_field(line: str, is_a_field: bool):
    """
    Each docstring line is listed beside whether it starts a field.
    """
    assert (SourceProse.field_list_item.match(line) is not None) is is_a_field


@pytest.mark.parametrize(
    ("comment", "is_for_a_tool"),
    [
        (f"# {ToolDirective.LINT_SUPPRESSION}: E501", True),
        (f"#{ToolDirective.TYPE_COMMENT} ignore", True),
        (f"# {ToolDirective.INTERPRETER}/usr/bin/env", True),
        ("# the noqa rule explained", False),
        ("a line without a comment marker", False),
    ],
)
def test_a_comment_addressed_to_a_tool_is_told_from_one_for_a_reader(
    comment: str, is_for_a_tool: bool
):
    """
    Each comment is listed beside whether a tool reads it.
    """
    assert (SourceProse.tool_directive.match(comment) is not None) is is_for_a_tool


# %% installed libraries


@pytest.mark.parametrize(
    ("requirement", "needs_an_extra"),
    [
        ("pydantic>=2; extra == 'email'", True),
        ('lib ; python_version < "3.13" and extra=="dev"', True),
        ("pydantic>=2", False),
        ("lib ; python_version < '3.13'", False),
        ("lib ; extras_marker == 'x'", False),
    ],
)
def test_a_requirement_only_an_extra_brings_in_is_told_by_its_marker(
    requirement: str, needs_an_extra: bool
):
    """
    Each requirement is listed beside whether only an extra requires it.
    """
    assert (EXTRA_MARKER.search(requirement) is not None) is needs_an_extra


@pytest.mark.parametrize(
    ("name", "canonical"),
    [
        ("Typing_Extensions", "typing-extensions"),
        ("ruamel.yaml", "ruamel-yaml"),
        ("a__b--c..d", "a-b-c-d"),
        ("plain", "plain"),
    ],
)
def test_a_distribution_name_is_canonical_in_lower_case_with_hyphens(
    name: str, canonical: str
):
    """
    Each name is listed beside its canonical spelling.
    """
    assert InstalledLibraries.canonical_distribution_name(name) == canonical
