"""
Tests for the plan page's re-check of the Contribute button: what its pull request's
draft state, and an override of its failed checks, show in the browser.
"""

from __future__ import annotations

import re
from http import HTTPStatus
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from basstler.github.pull_request_record import PullRequestField
from basstler.github.states import CombinedCheckState
from basstler.github.pull_request_state import (
    ForkLineage,
    PullRequestRecord,
    PullRequestState,
)
from basstler.plan_site.__main__ import RepositorySite
from basstler.plan_site.cards import PromotionAttribute
from basstler.stack.promotability import PromotionBlocker

from ..constants.stack import StackLabel
from ..github.pull_request_api import api_pull_request
from ..recorded_pull_requests import RecordedPullRequestSource
from .first_plan import OPEN_PULL_REQUEST, PLAN_REPOSITORY
from .test_live_states import answers_with, open_first_plan_page, open_item_card

# %% a plan in a fork

LINEAGE = ForkLineage(
    upstream_repository=PLAN_REPOSITORY,
    upstream_default_branch="trunk",
    fork_default_branch="main",
)
"""
What the first plan's repository was forked from.
"""

CONTRIBUTE = ".promote-button"
"""
The Contribute button on an item's card.
"""

PROMOTION_REASON = ".promote-reason"
"""
The text saying why the Contribute button is disabled.
"""

CHECKS_OVERRIDE = f"[{PromotionAttribute.CHECKS_OVERRIDE}]"
"""
The checkbox declaring an item ready despite its failed checks.
"""


@pytest.fixture
def a_fork_source(
    pull_request_source: RecordedPullRequestSource,
) -> RecordedPullRequestSource:
    """
    The first plan's pull request source, whose repository is a fork and whose open
    pull request is stacked on the fork's default branch.
    """
    pull_request_source.fork_lineages[PLAN_REPOSITORY] = LINEAGE
    pull_request_source.records[OPEN_PULL_REQUEST] = PullRequestRecord(
        state=PullRequestState.OPEN, draft=True, base=LINEAGE.fork_default_branch
    )
    return pull_request_source


# %% a draft that was marked ready since the build


def test_a_pull_request_marked_ready_since_the_build_enables_its_button(
    a_fork_source: RecordedPullRequestSource,
    site: RepositorySite,
    browser_page: Page,
    tmp_path: Path,
):
    site.build(tmp_path)
    ready = api_pull_request(OPEN_PULL_REQUEST, {PullRequestField.DRAFT: False})

    open_first_plan_page(browser_page, tmp_path, answers_with((HTTPStatus.OK, ready)))

    button = open_item_card(browser_page).locator(CONTRIBUTE)
    expect(button).not_to_have_class("promote-button promote-button-disabled")
    expect(button).to_have_attribute("href", re.compile(".+"))
    expect(open_item_card(browser_page).locator(PROMOTION_REASON)).to_have_text("")


def test_a_pull_request_still_a_draft_keeps_its_button_disabled(
    a_fork_source: RecordedPullRequestSource,
    site: RepositorySite,
    browser_page: Page,
    tmp_path: Path,
):
    site.build(tmp_path)
    draft = api_pull_request(OPEN_PULL_REQUEST, {PullRequestField.DRAFT: True})

    open_first_plan_page(browser_page, tmp_path, answers_with((HTTPStatus.OK, draft)))

    expect(open_item_card(browser_page).locator(PROMOTION_REASON)).to_have_text(
        PromotionBlocker.DRAFT.value
    )


# %% a ready pull request that was turned back into a draft


def test_a_pull_request_turned_back_into_a_draft_disables_its_button(
    a_fork_source: RecordedPullRequestSource,
    site: RepositorySite,
    browser_page: Page,
    tmp_path: Path,
):
    a_fork_source.records[OPEN_PULL_REQUEST] = PullRequestRecord(
        state=PullRequestState.OPEN, draft=False, base=LINEAGE.fork_default_branch
    )
    site.build(tmp_path)
    draft = api_pull_request(OPEN_PULL_REQUEST, {PullRequestField.DRAFT: True})

    open_first_plan_page(browser_page, tmp_path, answers_with((HTTPStatus.OK, draft)))

    expect(open_item_card(browser_page).locator(PROMOTION_REASON)).to_have_text(
        PromotionBlocker.DRAFT.value
    )


# %% overriding failed checks


@pytest.fixture
def a_failing_fork_source(
    a_fork_source: RecordedPullRequestSource,
) -> RecordedPullRequestSource:
    """
    The fork's open pull request out of draft, its checks failed.
    """
    a_fork_source.records[OPEN_PULL_REQUEST] = PullRequestRecord(
        state=PullRequestState.OPEN,
        draft=False,
        base=LINEAGE.fork_default_branch,
        check_state=CombinedCheckState.FAILURE,
    )
    return a_fork_source


def open_failing_item_card(browser_page: Page, output: Path):
    """
    :param browser_page: The browser page to open the built site in.
    :param output: The built site's root directory.
    :return: The open item's card, its pull request answered as out of draft.
    """
    ready = api_pull_request(OPEN_PULL_REQUEST, {PullRequestField.DRAFT: False})
    open_first_plan_page(browser_page, output, answers_with((HTTPStatus.OK, ready)))
    return open_item_card(browser_page)


def test_overriding_failed_checks_enables_the_button(
    a_failing_fork_source: RecordedPullRequestSource,
    site: RepositorySite,
    browser_page: Page,
    tmp_path: Path,
):
    site.build(tmp_path)
    card = open_failing_item_card(browser_page, tmp_path)

    card.locator(CHECKS_OVERRIDE).check()

    expect(card.locator(CONTRIBUTE)).to_have_attribute("href", re.compile(".+"))
    expect(card.locator(PROMOTION_REASON)).to_have_text("")


def test_withdrawing_the_override_disables_the_button_again(
    a_failing_fork_source: RecordedPullRequestSource,
    site: RepositorySite,
    browser_page: Page,
    tmp_path: Path,
):
    site.build(tmp_path)
    card = open_failing_item_card(browser_page, tmp_path)

    card.locator(CHECKS_OVERRIDE).check()
    card.locator(CHECKS_OVERRIDE).uncheck()

    expect(card.locator(CONTRIBUTE)).not_to_have_attribute("href", re.compile(".*"))
    expect(card.locator(PROMOTION_REASON)).to_have_text(
        PromotionBlocker.CHECKS_FAILED.value
    )


def test_overriding_failed_checks_leaves_every_other_blocker(
    a_failing_fork_source: RecordedPullRequestSource,
    site: RepositorySite,
    browser_page: Page,
    tmp_path: Path,
):
    a_failing_fork_source.records[OPEN_PULL_REQUEST].labels.append(
        StackLabel.NEEDS_RESOLUTION.value
    )
    site.build(tmp_path)
    card = open_failing_item_card(browser_page, tmp_path)

    card.locator(CHECKS_OVERRIDE).check()

    expect(card.locator(CONTRIBUTE)).not_to_have_attribute("href", re.compile(".*"))
    expect(card.locator(PROMOTION_REASON)).to_have_text(PromotionBlocker.WITHHELD.value)


def test_overriding_failed_checks_keeps_a_draft_disabled(
    a_failing_fork_source: RecordedPullRequestSource,
    site: RepositorySite,
    browser_page: Page,
    tmp_path: Path,
):
    site.build(tmp_path)
    draft = api_pull_request(OPEN_PULL_REQUEST, {PullRequestField.DRAFT: True})
    open_first_plan_page(browser_page, tmp_path, answers_with((HTTPStatus.OK, draft)))
    card = open_item_card(browser_page)

    card.locator(CHECKS_OVERRIDE).check()

    expect(card.locator(PROMOTION_REASON)).to_have_text(PromotionBlocker.DRAFT.value)


def test_overriding_failed_checks_works_when_github_refuses_the_recheck(
    a_failing_fork_source: RecordedPullRequestSource,
    site: RepositorySite,
    browser_page: Page,
    tmp_path: Path,
):
    site.build(tmp_path)
    open_first_plan_page(
        browser_page, tmp_path, answers_with((HTTPStatus.NOT_FOUND, {}))
    )
    card = open_item_card(browser_page)

    card.locator(CHECKS_OVERRIDE).check()

    expect(card.locator(CONTRIBUTE)).to_have_attribute("href", re.compile(".+"))
