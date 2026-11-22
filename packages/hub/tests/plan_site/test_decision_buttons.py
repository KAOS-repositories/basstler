"""
Tests for the buttons that answer an owner's decision on the plan site's pages.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from basstler.plan.decision import Decision, DecisionOption
from basstler.plan.dependencies import PlanDirectory
from basstler.plan.goal import Goal
from basstler.plan.structure import Item
from basstler.plan_site.__main__ import SiteFile

from basstler_testing.constants.paths import DatasetLocation
from basstler_testing.recorded_pull_requests import RecordedPullRequestSource
from .test_goal_page import (
    ADDRESS,
    NOTES_REPOSITORY,
    build_site,
    page_at,
    plan_files_under,
)

PLAN_ID = "review-experiment"
"""
The dataset plan whose one item asks for a verdict.
"""

GOAL = Goal.from_yaml(
    (DatasetLocation.DECISION_PLANS / "_goals" / "experiment-decided.yaml").read_text(encoding="utf-8")
)
"""
The goal behind the verdict.
"""

REQUEST = "Make the path numbers larger"
"""
What the owner writes into the request box.
"""

RECORD_COPIES = """
window.copiedTexts = [];
Object.defineProperty(navigator, "clipboard", {
  value: {writeText: (text) => { window.copiedTexts.push(text); return Promise.resolve(); }},
});
"""
"""
Replaces the clipboard with one that keeps every text written to it.
"""

# %% the site


@pytest.fixture
def verdict_item() -> Item:
    """
    :return: The dataset item that asks for a verdict.
    """
    (item,) = PlanDirectory(DatasetLocation.DECISION_PLANS).plan(PLAN_ID).items
    return item


@pytest.fixture
def options(verdict_item: Item) -> tuple[DecisionOption, ...]:
    """
    :param verdict_item: The item that asks for a verdict.
    :return: The options that answer it.
    """
    assert verdict_item.decision is Decision.EXPERIMENT_VERDICT
    return verdict_item.decision.options


@pytest.fixture
def built_site(tmp_path: Path) -> Path:
    """
    :param tmp_path: A directory of the test's own.
    :return: The directory a site over the decision plans was built under.
    """
    build_site(
        tmp_path,
        plan_files_under(DatasetLocation.DECISION_PLANS.value),
        RecordedPullRequestSource(),
    )
    return tmp_path


def invocation_of(option: DecisionOption, verdict_item: Item) -> str:
    """
    :param option: One way to answer the verdict.
    :param verdict_item: The item that asks for it.
    :return: The skill command that option copies.
    """
    return option.invocation(PLAN_ID, verdict_item.identifier)


# %% the markup


class TestDecisionButtonsInThePages:
    """
    Every page showing the owner's step offers one button per option.
    """

    @pytest.mark.parametrize("page_url", ["goal", "plan"])
    def test_each_option_is_a_button_carrying_its_command(
        self,
        built_site: Path,
        options: tuple[DecisionOption, ...],
        verdict_item: Item,
        page_url: str,
    ):
        """
        The page carries each option's label and command, the command attributed.
        """
        url = {
            "goal": ADDRESS.goal_url(NOTES_REPOSITORY, GOAL.identifier),
            "plan": ADDRESS.plan_url(NOTES_REPOSITORY, PLAN_ID),
        }[page_url]
        page = page_at(built_site, url)
        for option in options:
            command = html.escape(invocation_of(option, verdict_item))
            assert f'data-decision-prompt="{command}"' in page
            assert f"▸ {html.escape(option.label)}</button>" in page

    def test_only_the_options_asking_for_a_request_are_marked(
        self,
        built_site: Path,
        options: tuple[DecisionOption, ...],
        verdict_item: Item,
    ):
        """
        The goal's page marks exactly the buttons that need the owner's request.
        """
        page = page_at(built_site, ADDRESS.goal_url(NOTES_REPOSITORY, GOAL.identifier))
        marked = {
            option.argument: all(
                "data-asks-for-request" in tag
                for tag in re.findall(
                    rf"<button[^>]*{re.escape(html.escape(invocation_of(option, verdict_item)))}\"[^>]*>",
                    page,
                )
            )
            for option in options
        }
        assert marked == {
            option.argument: option.asks_for_request for option in options
        }


# %% copying


def open_goal_page(browser_page: Page, built_site: Path) -> None:
    """
    :param browser_page: The browser page to open it in.
    :param built_site: The directory the site was built under.
    """
    browser_page.add_init_script(RECORD_COPIES)
    relative = ADDRESS.goal_url(NOTES_REPOSITORY, GOAL.identifier).removeprefix(
        ADDRESS.hub_url
    )
    browser_page.goto((built_site / "site" / relative / SiteFile.PAGE).as_uri())


class TestCopyingADecision:
    """
    A decision button copies its skill command, followed by the owner's request.
    """

    def test_an_option_needing_no_request_copies_only_its_command(
        self,
        built_site: Path,
        browser_page: Page,
        options: tuple[DecisionOption, ...],
        verdict_item: Item,
    ):
        """
        Without a request written, the clipboard holds the bare command.
        """
        (option,) = [o for o in options if not o.asks_for_request][:1]
        open_goal_page(browser_page, built_site)
        browser_page.locator(
            f'[data-decision-prompt="{invocation_of(option, verdict_item)}"]'
        ).first.click()
        assert browser_page.evaluate("window.copiedTexts") == [
            invocation_of(option, verdict_item)
        ]

    def test_a_written_request_follows_the_command(
        self,
        built_site: Path,
        browser_page: Page,
        options: tuple[DecisionOption, ...],
        verdict_item: Item,
    ):
        """
        The clipboard holds the command, a blank line, then the request.
        """
        (option,) = [o for o in options if o.asks_for_request]
        open_goal_page(browser_page, built_site)
        card = browser_page.locator(".decision").last
        card.locator(".decision-request").fill(REQUEST)
        card.locator("[data-asks-for-request]").click()
        assert browser_page.evaluate("window.copiedTexts") == [
            f"{invocation_of(option, verdict_item)}\n\n{REQUEST}"
        ]

    def test_an_option_needing_a_request_copies_nothing_without_one(
        self, built_site: Path, browser_page: Page
    ):
        """
        With the request box empty, the button copies nothing and flags the box.
        """
        open_goal_page(browser_page, built_site)
        card = browser_page.locator(".decision").last
        card.locator("[data-asks-for-request]").click()
        assert browser_page.evaluate("window.copiedTexts") == []
        expect(card.locator(".decision-request")).to_have_class(
            "decision-request decision-request-missing"
        )
