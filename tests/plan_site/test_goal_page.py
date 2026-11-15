"""
Tests for basstler.plan_site's goal pages and the goals a repository's index lists.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import pytest
import yaml
from playwright.sync_api import Page, Route, expect

from basstler.github.pull_request_record import PullRequestField
from basstler.github.pull_request_state import LiveState

from basstler.github.pull_request_source import PullRequestSource
from basstler.locations import ProjectLocation
from basstler.plan.dependencies import DependencyReference, PlanDirectory
from basstler.plan.exceptions import UnresolvedGoalReferenceError
from basstler.plan.goal import Goal
from basstler.github.repository import PullRequestReference
from basstler.plan.goal_path import GoalCommandName, GoalPath, NeededItems, PathStep
from basstler.plan.model import PlanDocument
from basstler.plan_site.__main__ import RepositorySite, SiteFile
from basstler.plan_site.cards import (
    DraftRecheckAttribute,
    LiveStateAttribute,
    PlanTimeAttribute,
    RefreshSource,
)
from basstler.plan_site.goal_page import GoalPage, GoalSummary
from basstler.plan_site.hub import NotesBranch, SiteAddress
from basstler.plan_site.hub_page import RepositorySummary
from basstler.setup.steps import PersonalNotesSetting

from ..constants.paths import DatasetLocation
from ..constants.site import SiteRepository, SiteSampleText
from ..github.pull_request_api import api_pull_request
from ..plan.test_goal_path import GOAL, recorded_pull_requests
from ..plan import test_merged_dependencies as merged_dependency_plan
from ..plan.test_owner_steps import GOAL as OWNER_STEP_GOAL
from ..plan.test_owner_steps import PLAN_ID as OWNER_STEP_PLAN_ID
from ..recorded_pull_requests import RecordedPullRequestSource
from .test_build_site import link_to
from .test_hub import publish_notes

NOTES_REPOSITORY = SiteRepository.NOTES.value
"""
The repository whose notes hold the goal and the plans it spans.
"""

ADDRESS = SiteAddress(SiteSampleText.SITE_URL)
"""
The address the site under test is served from.
"""

UNRESOLVED_GOAL = Goal(
    identifier="names-nothing", title="Unreachable", targets=["no-plan/no-item"]
)
"""
A goal whose only target names no item.
"""

# %% a site over the goal's plans


def goal_plan_files() -> dict[Path, str]:
    """
    :return: Every file of the dataset's goal plans, by its path in the plans directory.
    """
    return plan_files_under(DatasetLocation.GOAL_PLANS.value)


def plan_files_under(directory: Path) -> dict[Path, str]:
    """
    :param directory: A dataset plans directory.
    :return: Every file under it, by its path in the plans directory.
    """
    return {
        path.relative_to(directory): path.read_text()
        for path in directory.rglob("*")
        if path.is_file()
    }


def build_site(
    tmp_path: Path,
    files: dict[Path, str],
    pull_request_source: PullRequestSource | None = None,
) -> RepositorySummary:
    """
    :param tmp_path: A directory of the test's own.
    :param files: The notes branch's plans directory.
    :param pull_request_source: Where the build reads pull requests from; every dataset
        pull request a draft when not given.
    :return: The card of the repository built into ``tmp_path / "site"``.
    """
    publish_notes(tmp_path / "remotes", NOTES_REPOSITORY, files)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    notes = NotesBranch.fetch(
        NOTES_REPOSITORY,
        PersonalNotesSetting.BRANCH.default,
        str(tmp_path / "remotes"),
        scratch,
    )
    site = RepositorySite(
        address=ADDRESS,
        pull_request_source=pull_request_source or recorded_pull_requests(draft=True),
        notes=notes,
    )
    return site.build(tmp_path / "site")


def page_at(tmp_path: Path, url: str) -> str:
    """
    :param tmp_path: The directory :func:`build_site` built into.
    :param url: A page's address on the site.
    :return: That page's HTML.
    """
    relative = url.removeprefix(ADDRESS.hub_url)
    return (tmp_path / "site" / relative / SiteFile.PAGE).read_text()


@pytest.fixture
def goal_path() -> GoalPath:
    """
    :return: The dataset goal's path, every pull request a draft.
    """
    return GoalPath.compute(
        GOAL,
        PlanDirectory(DatasetLocation.GOAL_PLANS),
        recorded_pull_requests(draft=True),
    )


GOAL_URL = ADDRESS.goal_url(NOTES_REPOSITORY, GOAL.identifier)
"""
Where the dataset goal's page is served from.
"""


# %% the goal's page


class TestTheGoalPage:
    """
    A goal's page shows the path's steps, each linked to its item and its command.
    """

    def test_the_site_publishes_the_goal_at_its_address(self, tmp_path: Path):
        """
        A built site serves the goal's page, titled with the goal.
        """
        build_site(tmp_path, goal_plan_files())
        assert f"<h1>{html.escape(GOAL.title)}</h1>" in page_at(tmp_path, GOAL_URL)

    def test_every_step_links_to_its_item_card(
        self, tmp_path: Path, goal_path: GoalPath
    ):
        """
        Each step of the path links to its item's card on its plan's page.
        """
        build_site(tmp_path, goal_plan_files())
        page = page_at(tmp_path, GOAL_URL)
        for step in goal_path.steps:
            card_url = ADDRESS.item_url(
                NOTES_REPOSITORY,
                step.reference.plan_id,
                step.reference.item_identifier,
            )
            assert link_to(card_url) in page

    def test_every_step_with_an_action_carries_its_command(
        self, tmp_path: Path, goal_path: GoalPath
    ):
        """
        A step that can be acted on shows the command that carries it out.
        """
        build_site(tmp_path, goal_plan_files())
        page = page_at(tmp_path, GOAL_URL)
        commands = [step.action.command for step in goal_path.steps if step.action]
        assert commands
        for command in commands:
            assert f'data-action-command="{command}"' in page

    def test_every_step_with_a_pull_request_links_it(
        self, tmp_path: Path, goal_path: GoalPath
    ):
        """
        A step whose item has a pull request links that pull request.
        """
        build_site(tmp_path, goal_plan_files())
        page = page_at(tmp_path, GOAL_URL)
        references = [
            step.pull_request_reference
            for step in goal_path.steps
            if step.pull_request_reference
        ]
        assert references
        for reference in references:
            assert link_to(reference.url) in page

    def test_every_owner_move_is_shown(self, tmp_path: Path, goal_path: GoalPath):
        """
        A step whose pull request waits on the owner shows the owner's move.
        """
        build_site(tmp_path, goal_plan_files())
        page = page_at(tmp_path, GOAL_URL)
        moves = [
            step.owner_move.description for step in goal_path.steps if step.owner_move
        ]
        assert moves
        for move in moves:
            assert html.escape(move) in page

    def test_a_waiting_group_links_the_steps_it_waits_for(self, goal_path: GoalPath):
        """
        A group's heading links each awaited step's place on the page.
        """
        waiting = next(group for group in goal_path.groups if group.awaited)
        assert GoalPage.anchor_of(waiting.awaited[0]) == (
            f"step-{waiting.awaited[0].plan_id}-{waiting.awaited[0].item_identifier}"
        )


# %% the repository's index


class TestTheGoalsOnTheIndex:
    """
    A repository's index lists its goals, and names the ones the build left out.
    """

    def test_the_index_links_the_goal_and_shows_its_next_move(
        self, tmp_path: Path, goal_path: GoalPath
    ):
        """
        The index links the goal's page beside its next command.
        """
        build_site(tmp_path, goal_plan_files())
        index = page_at(tmp_path, ADDRESS.repository_url(NOTES_REPOSITORY))
        assert link_to(GOAL_URL) in index
        assert f"<code>{goal_path.next_step.next_move}</code>" in index

    def test_a_summary_counts_the_finished_steps(self):
        """
        A goal's entry counts the steps whose pull requests merged.
        """
        merged = frozenset({"move-triage", "rule-fixes"})
        path = GoalPath.compute(
            GOAL,
            PlanDirectory(DatasetLocation.GOAL_PLANS),
            recorded_pull_requests(draft=True, merged_items=merged),
        )
        summary = GoalSummary.from_path(path, GOAL_URL)
        assert summary.finished_step_count == len(merged)
        assert summary.step_count == len(path.steps)

    def test_a_goal_naming_no_item_is_left_out_and_reported(self, tmp_path: Path):
        """
        A goal with an unresolved target gets no page and is named as skipped.
        """
        files = goal_plan_files() | {
            Path(ProjectLocation.PLAN_GOALS.name)
            / f"{UNRESOLVED_GOAL.identifier}.yaml": UNRESOLVED_GOAL.render()
        }
        repository = build_site(tmp_path, files)
        skipped_path = ADDRESS.goal_url(
            NOTES_REPOSITORY, UNRESOLVED_GOAL.identifier
        ).removeprefix(ADDRESS.hub_url)
        assert skipped_path.rstrip("/") in [
            page.site_path for page in repository.skipped_pages
        ]
        assert not (tmp_path / "site" / skipped_path).exists()

    def test_unresolved_references_are_collected_not_raised(self):
        """
        Resolving a goal's items records each reference that names nothing.
        """
        needed = NeededItems.of_goal(
            UNRESOLVED_GOAL, PlanDirectory(DatasetLocation.GOAL_PLANS)
        )
        assert [problem.reference_text for problem in needed.unresolved] == (
            UNRESOLVED_GOAL.targets
        )
        with pytest.raises(UnresolvedGoalReferenceError):
            needed.refuse_unresolved_references()


# %% a step the owner performs


class TestAnOwnersStepOnTheSite:
    """
    The commands of a step the owner performs are shown wherever the step is.
    """

    @pytest.fixture
    def commands(self) -> list[str]:
        """
        :return: Every command the dataset plan records for its owner.
        """
        plan = PlanDirectory(DatasetLocation.OWNER_STEP_PLANS).plan(OWNER_STEP_PLAN_ID)
        commands = [command for item in plan.items for command in item.commands]
        assert commands
        return commands

    @pytest.fixture
    def built_site(self, tmp_path: Path) -> Path:
        """
        :return: The directory a site over the owner-step plans was built under.
        """
        build_site(
            tmp_path,
            plan_files_under(DatasetLocation.OWNER_STEP_PLANS.value),
            RecordedPullRequestSource(),
        )
        return tmp_path

    def test_the_goal_page_lists_the_commands(
        self, built_site: Path, commands: list[str]
    ):
        """
        The goal's page shows each command of the owner's step.
        """
        page = page_at(
            built_site, ADDRESS.goal_url(NOTES_REPOSITORY, OWNER_STEP_GOAL.identifier)
        )
        for command in commands:
            assert f"<code>{html.escape(command)}</code>" in page

    def test_the_goal_page_names_the_closing_command(self, built_site: Path):
        """
        The goal's page shows the command that records the owner's step as done.
        """
        page = page_at(
            built_site, ADDRESS.goal_url(NOTES_REPOSITORY, OWNER_STEP_GOAL.identifier)
        )
        closing = GoalCommandName.CHECK.invocation(OWNER_STEP_GOAL.identifier)
        assert f"<code>{closing}</code>" in page

    def test_the_plan_page_lists_the_commands(
        self, built_site: Path, commands: list[str]
    ):
        """
        The plan's page shows each command on the owner's step's card.
        """
        page = page_at(
            built_site, ADDRESS.plan_url(NOTES_REPOSITORY, OWNER_STEP_PLAN_ID)
        )
        for command in commands:
            assert f"<code>{html.escape(command)}</code>" in page


# %% a step waiting for a merge


class TestAStepWaitingForAMerge:
    """
    A step that needs a dependency merged says so on the goal's page.
    """

    def test_the_goal_page_names_the_awaited_merge(self, tmp_path: Path):
        """
        The dependent's card links the step whose merge it starts after.
        """
        goal = merged_dependency_plan.GOAL
        (target,) = goal.target_references
        records = merged_dependency_plan.base_pull_request(merged=False)
        build_site(
            tmp_path,
            {
                Path(target.plan_id) / PlanDocument.MANIFEST: yaml.safe_dump(
                    merged_dependency_plan.manifest()
                ),
                Path(ProjectLocation.PLAN_GOALS.name) / f"{goal.identifier}.yaml": (
                    goal.render()
                ),
            },
            RecordedPullRequestSource(records=records),
        )
        page = page_at(tmp_path, ADDRESS.goal_url(NOTES_REPOSITORY, goal.identifier))
        base = DependencyReference(
            item_identifier=merged_dependency_plan.BASE, plan_id=target.plan_id
        )
        awaited_link = f'<a class="chip" {link_to("#" + GoalPage.anchor_of(base))}>'
        assert f"Starts once merged: {awaited_link}{base.text}</a>" in page


# %% the sequence and whose turn each step is


class TestTheSequenceOnTheGoalPage:
    """
    The goal's page numbers every unfinished step and says who moves it now.
    """

    def test_every_unfinished_step_carries_its_place(
        self, tmp_path: Path, goal_path: GoalPath
    ):
        """
        Each step's card leads with its place in the recommended sequence.
        """
        build_site(tmp_path, goal_plan_files())
        page = page_at(tmp_path, GOAL_URL)
        assert goal_path.sequence
        for step in goal_path.sequence:
            position = goal_path.position_of(step)
            assert f'<span class="step-number">{position}.</span> <a ' in page
        assert page.count('<span class="step-number">') == len(goal_path.sequence)

    def test_the_next_step_that_is_the_owners_shows_the_move_not_a_command_button(
        self, tmp_path: Path, goal_path: GoalPath
    ):
        """
        When the next step waits on the owner, the page's next section states the move.
        """
        build_site(tmp_path, goal_plan_files())
        page = page_at(tmp_path, GOAL_URL)
        next_section = page.split('id="goal-next-step"')[1].split("</section>")[0]
        assert goal_path.next_step.is_owners_turn
        assert html.escape(goal_path.next_step.owner_move.description) in next_section
        assert "action-button" not in next_section.split("Yours now")[0]

    def test_a_step_is_marked_with_whose_move_it_is(
        self, tmp_path: Path, goal_path: GoalPath
    ):
        """
        The cards marked as the owner's move are as many as the owner's steps.
        """
        build_site(tmp_path, goal_plan_files())
        page = page_at(tmp_path, GOAL_URL)
        assert page.count("Your move</span>") == len(goal_path.owner_steps)
        assert page.count("A session's move</span>") == len(
            [step for step in goal_path.sequence if step.needs_a_session]
        )


# %% the page's refresh


ANSWERED_PULL_REQUEST = PullRequestReference(NOTES_REPOSITORY, 1)
"""
The pull request GitHub's stand-in describes whichever address the page asks for.
"""


def first_draft_step(goal_path: GoalPath) -> PathStep:
    """
    :return: The first step of the path whose pull request is a draft.
    """
    return next(
        step
        for step in goal_path.sequence
        if step.item.live_state is LiveState.OPEN_DRAFT
    )


def open_goal_page(page: Page, tmp_path: Path, overrides: dict) -> None:
    """
    Open the built goal page with GitHub answering every pull request as an open draft
    changed by ``overrides``, and wait for the page's re-check.

    :param page: The browser page to open it in.
    :param tmp_path: The directory :func:`build_site` built into.
    :param overrides: The fields GitHub answers differently from an open draft.
    """
    fields = {PullRequestField.DRAFT: True, **overrides}

    def answer_for_github(route: Route) -> None:
        route.fulfill(
            headers={"Access-Control-Allow-Origin": "*"},
            content_type="application/json",
            body=json.dumps(api_pull_request(ANSWERED_PULL_REQUEST, fields)),
        )

    page.route(SiteSampleText.SITE_URL + "**", lambda route: route.abort())
    page.route("https://api.github.com/**", answer_for_github)
    relative = GOAL_URL.removeprefix(ADDRESS.hub_url)
    page.goto((tmp_path / "site" / relative / SiteFile.PAGE).as_uri())
    page.wait_for_selector(f"[{DraftRecheckAttribute.FINISHED}]", state="attached")


class TestTheGoalPagesRefresh:
    """
    The goal's page says when its states were read and re-reads them when opened.
    """

    def test_the_page_says_when_it_was_built(self, tmp_path: Path):
        """
        The masthead carries the refresh time, marked as coming from the build.
        """
        build_site(tmp_path, goal_plan_files())
        page = page_at(tmp_path, GOAL_URL)
        assert f"Refreshed <time {PlanTimeAttribute.RELATIVE} " in page
        assert (
            f"<span {PlanTimeAttribute.REFRESH_SOURCE}>{RefreshSource.BUILD}</span>"
            in page
        )

    def test_every_pull_request_chip_names_its_api_address(
        self, tmp_path: Path, goal_path: GoalPath
    ):
        """
        Each step's pull request chip carries the address its state is re-read from.
        """
        build_site(tmp_path, goal_plan_files())
        page = page_at(tmp_path, GOAL_URL)
        references = [
            step.pull_request_reference
            for step in goal_path.sequence
            if step.pull_request_reference
        ]
        assert references
        for reference in references:
            assert f'{LiveStateAttribute.PULL_REQUEST}="{reference.api_url}"' in page

    def test_unchanged_pull_requests_refresh_the_time_and_show_no_notice(
        self, tmp_path: Path, browser_page: Page
    ):
        """
        When GitHub answers what the build read, only the refresh time changes.
        """
        build_site(tmp_path, goal_plan_files())
        open_goal_page(browser_page, tmp_path, {})
        expect(
            browser_page.locator(f"[{PlanTimeAttribute.REFRESH_SOURCE}]")
        ).to_have_text(RefreshSource.LIVE)
        expect(
            browser_page.locator(f"[{LiveStateAttribute.CHANGED_SINCE_BUILD}]")
        ).to_be_hidden()

    def test_a_pull_request_changed_since_the_build_is_shown_and_announced(
        self, tmp_path: Path, browser_page: Page, goal_path: GoalPath
    ):
        """
        A draft now out of draft shows as ready, and the page says its order is stale.
        """
        build_site(tmp_path, goal_plan_files())
        open_goal_page(browser_page, tmp_path, {PullRequestField.DRAFT: False})
        step = first_draft_step(goal_path)
        chip = browser_page.locator(
            f"#{GoalPage.anchor_of(step.reference)} [{LiveStateAttribute.PULL_REQUEST}]"
        )
        expect(chip).to_contain_text(LiveState.OPEN_READY.display_label)
        expect(
            browser_page.locator(f"[{LiveStateAttribute.CHANGED_SINCE_BUILD}]")
        ).to_be_visible()
