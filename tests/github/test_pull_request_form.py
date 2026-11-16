"""
GitHub's pull request form, filled in from its address.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from basstler.git.branch import Branch
from basstler.github.pull_request_form import PullRequestForm, PullRequestFormParameter
from basstler.github.repository import Repository

# %% the filled-in form

FORM = PullRequestForm(
    Repository("an-owner", "a-project"),
    Branch("main"),
    Branch("a-branch"),
    "Add a workflow",
    "It marks files viewed.",
)
"""
A form for one branch with a short title and description.
"""


def test_the_form_fills_in_the_title_and_description():
    query = parse_qs(urlsplit(FORM.link.url).query)
    assert (
        query[PullRequestFormParameter.TITLE],
        query[PullRequestFormParameter.BODY],
    ) == ([FORM.title], [FORM.body])


def test_the_form_compares_the_branch_with_its_base():
    assert FORM.link.url.startswith(
        f"{FORM.repository.compare_url(FORM.base, FORM.head)}?"
    )


def test_a_branch_on_a_fork_is_compared_under_its_owner():
    form = PullRequestForm(
        FORM.repository, FORM.base, FORM.head, FORM.title, FORM.body, "a-forker"
    )
    assert form.link.url.startswith(
        f"{FORM.repository.compare_url(FORM.base, FORM.head, 'a-forker')}?"
    )


# %% shortening the description


def test_a_shortened_description_keeps_every_character_that_fits():
    """
    The body's characters encode to different lengths, so the cut is where one more
    character would push the URL over the limit.
    """
    form = PullRequestForm(
        FORM.repository,
        FORM.base,
        FORM.head,
        FORM.title,
        "a é ✓ " * PullRequestForm.url_character_limit,
    )
    kept = parse_qs(urlsplit(form.link.url).query)[PullRequestFormParameter.BODY][0]
    kept = kept.removesuffix(PullRequestForm.truncation_marker)
    one_more = PullRequestForm(
        form.repository,
        form.base,
        form.head,
        form.title,
        form.body[: len(kept) + 1] + PullRequestForm.truncation_marker,
    )
    assert len(form.link.url) <= PullRequestForm.url_character_limit < len(one_more.url)
