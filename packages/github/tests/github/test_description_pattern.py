"""
Tests for :class:`basstler.github.constants.DescriptionPattern`: what the tooling looks
for in a pull request description.
"""

from __future__ import annotations

import pytest

from basstler.github.constants import DescriptionPattern

# %% the session link


@pytest.mark.parametrize(
    ("description", "link"),
    [
        (
            "Done.\n\nhttps://claude.ai/code/session_01AbC-d_9\n",
            "https://claude.ai/code/session_01AbC-d_9",
        ),
        (
            "[session](https://claude.ai/code/session_x1) and more",
            "https://claude.ai/code/session_x1",
        ),
        ("https://claude.ai/code/session_", None),
        ("https://claude.ai/chat/session_x1", None),
        ("no link here", None),
        (None, None),
    ],
)
def test_the_session_link_is_read_off_a_description(
    description: str | None, link: str | None
):
    """
    Each description is listed beside the link found in it.
    """
    assert DescriptionPattern.SESSION_LINK.first_in(description) == link


# %% a heading


@pytest.mark.parametrize(
    ("description", "heading_start"),
    [
        ("# Title", "# "),
        ("text\n### Notes", "### "),
        ("###### Deepest", "###### "),
        ("####### Seven", None),
        ("#NoSpace", None),
        ("text # not at the line start", None),
    ],
)
def test_a_heading_line_starts_with_one_to_six_markers_and_a_space(
    description: str, heading_start: str | None
):
    """
    Each text is listed beside the start of the heading line found in it.
    """
    assert DescriptionPattern.HEADING.first_in(description) == heading_start


# %% a link target


@pytest.mark.parametrize(
    ("description", "target"),
    [
        ("[text](https://example.com/a)", "https://example.com/a"),
        ("see [a](x/y) and [b](z)", "x/y"),
        ("[text](has space)", None),
        ("https://example.com/a", None),
        ("[text]()", None),
    ],
)
def test_the_target_of_a_markdown_link_is_read_without_its_brackets(
    description: str, target: str | None
):
    """
    Each text is listed beside the link target found in it.
    """
    assert DescriptionPattern.LINK_TARGET.first_in(description) == target
