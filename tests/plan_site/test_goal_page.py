"""
Tests for basstler.plan_site's goal pages and the goals a repository's index lists.
"""

from __future__ import annotations

import html
from pathlib import Path

import pytest

from basstler.locations import ProjectLocation
from basstler.plan.dependencies import PlanDirectory
from basstler.plan.exceptions import UnresolvedGoalReferenceError
from basstler.plan.goal import Goal
from basstler.plan.goal_path import GoalPath, NeededItems
from basstler.plan_site.__main__ import RepositorySite, SiteFile
from basstler.plan_site.goal_page import GoalPage, GoalSummary
from basstler.plan_site.hub import NotesBranch, SiteAddress
from basstler.plan_site.hub_page import RepositorySummary
from basstler.setup.steps import PersonalNotesSetting

from ..constants.paths import DatasetLocation
from ..constants.site import SiteRepository, SiteSampleText
from ..plan.test_goal_path import GOAL, recorded_pull_requests
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
    return {
        path.relative_to(DatasetLocation.GOAL_PLANS.value): path.read_text()
        for path in DatasetLocation.GOAL_PLANS.value.rglob("*")
        if path.is_file()
    }


def build_site(tmp_path: Path, files: dict[Path, str]) -> RepositorySummary:
    """
    :param tmp_path: A directory of the test's own.
    :param files: The notes branch's plans directory.
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
        pull_request_source=recorded_pull_requests(draft=True),
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

    def test_the_index_links_the_goal_and_shows_its_next_command(
        self, tmp_path: Path, goal_path: GoalPath
    ):
        """
        The index links the goal's page beside its next command.
        """
        build_site(tmp_path, goal_plan_files())
        index = page_at(tmp_path, ADDRESS.repository_url(NOTES_REPOSITORY))
        assert link_to(GOAL_URL) in index
        assert f"<code>{goal_path.next_step.action.command}</code>" in index

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
