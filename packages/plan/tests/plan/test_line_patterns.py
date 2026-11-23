"""
Tests for the patterns the plan tooling reads a ``plan.yaml``, a roadmap or a prose block
with: which lines have which shape, and how a block's text breaks into paragraphs.
"""

from __future__ import annotations

import pytest

from basstler.plan.item_bootstrap.vocabulary import ManifestLinePattern
from basstler.plan.model import ManifestKey, Prose
from basstler.plan.size_limits import RoadmapLine

# %% roadmap lines


@pytest.mark.parametrize(
    ("line", "shape"),
    [
        ("# Roadmap", RoadmapLine.TITLE),
        ("- A rule every item follows.", RoadmapLine.ENTRY),
        ("  continues the entry above", RoadmapLine.CONTINUATION),
        ("#Roadmap", None),
        ("-no space", None),
        ("   three spaces are no continuation", None),
        ("plain text", None),
        ("", None),
    ],
)
def test_a_roadmap_line_has_the_shape_its_start_gives_it(
    line: str, shape: RoadmapLine | None
):
    """
    Each line is listed beside the one shape it has.
    """
    shapes = [candidate for candidate in RoadmapLine if candidate.matches(line)]

    assert shapes == ([shape] if shape else [])


# %% manifest lines


@pytest.mark.parametrize(
    ("line", "shapes"),
    [
        (
            "  - id: first-item",
            {ManifestLinePattern.ITEM_START, ManifestLinePattern.SEQUENCE_ENTRY},
        ),
        ("    - one blocker", {ManifestLinePattern.SEQUENCE_ENTRY}),
        ("- flush entry", {ManifestLinePattern.SEQUENCE_ENTRY}),
        ("items:", {ManifestLinePattern.TOP_LEVEL_KEY}),
        ("    notes: >", {ManifestLinePattern.BLOCK_VALUE}),
        ("    branch: a/branch", set()),
        ("    -dash without a space", set()),
    ],
)
def test_a_manifest_line_is_matched_by_the_patterns_of_the_shape_it_has(
    line: str, shapes: set[ManifestLinePattern]
):
    """
    Each ``plan.yaml`` line is listed beside every shape it has.
    """
    matching = {pattern for pattern in ManifestLinePattern if pattern.matches(line)}

    assert matching == shapes


@pytest.mark.parametrize(
    ("line", "holds_the_key"),
    [
        ("    branch: claude/work", True),
        ("branch:", True),
        ("    branch:claude", True),
        ("    branches: x", False),
        ("    notes: branch: x", False),
        ("    # branch: x", False),
    ],
)
def test_a_key_is_found_where_it_starts_a_line_of_an_item_block(
    line: str, holds_the_key: bool
):
    """
    Each line is listed beside whether it holds the ``branch`` key.
    """
    assert (ManifestKey.BRANCH.pattern.match(line) is not None) is holds_the_key


# %% prose


@pytest.mark.parametrize(
    ("text", "paragraphs"),
    [
        ("one paragraph", ["one paragraph"]),
        ("first\n\nsecond", ["first", "second"]),
        ("first\n   \nsecond", ["first", "second"]),
        ("blank-\nline", ["blank-line"]),
        ("a suspended- hyphen", ["a suspended- hyphen"]),
        ("wrapped\nline", ["wrapped\nline"]),
    ],
)
def test_prose_breaks_into_paragraphs_and_closes_up_a_wrapped_hyphen(
    text: str, paragraphs: list[str]
):
    """
    Each text is listed beside the paragraphs it breaks into.
    """
    assert Prose(text).paragraphs == paragraphs
