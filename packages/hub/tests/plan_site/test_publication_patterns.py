"""
Tests for the patterns the plan site's publication reads text with: the line naming a
remote's default branch, and the element a plan page shows its build time in.
"""

from __future__ import annotations

import pytest

from basstler.plan_site.__main__ import SiteDigest
from basstler.plan_site.cards import PlanTimeAttribute
from basstler.plan_site.publication import SymbolicReferenceListing

# %% the line naming the default branch


@pytest.mark.parametrize(
    ("listing", "branch"),
    [
        ("ref: refs/heads/main\tHEAD\nabc123\tHEAD", "main"),
        ("ref: refs/heads/release/4.2\tHEAD", "release/4.2"),
        ("abc123\tHEAD\nref: refs/heads/trunk   HEAD", "trunk"),
        ("ref: refs/heads/main\tFETCH_HEAD", None),
        ("ref: refs/tags/v1\tHEAD", None),
        ("abc123\tHEAD", None),
        ("", None),
    ],
)
def test_the_default_branch_is_read_off_the_line_listing_head(
    listing: str, branch: str | None
):
    """
    Each ``ls-remote --symref`` listing is read beside the branch found in it.
    """
    found = SymbolicReferenceListing.default_branch_line().search(listing)

    assert (found[SymbolicReferenceListing.BRANCH_GROUP] if found else None) == branch


# %% the build time


@pytest.mark.parametrize(
    ("page", "removed"),
    [
        (
            f'<p><time {PlanTimeAttribute.REFRESHED} datetime="2026-11-23">now</time></p>',
            '<time {} datetime="2026-11-23">now</time>',
        ),
        (
            f"<time class=a {PlanTimeAttribute.REFRESHED}>x</time><time>y</time>",
            "<time class=a {}>x</time>",
        ),
        ("<time datetime='2026'>other</time>", None),
        ("<span>no time</span>", None),
    ],
)
def test_the_element_showing_the_build_time_is_the_only_one_removed(
    page: str, removed: str | None
):
    """
    Each page is listed beside the element taken out of it, ``None`` where none is.
    """
    expected = (
        page.replace(removed.format(PlanTimeAttribute.REFRESHED), "")
        if removed
        else page
    )

    assert SiteDigest.build_time_pattern.sub(b"", page.encode()) == expected.encode()
