"""
Tests for basstler.plan.goal_command: saving a goal on the notes branch and reading its
path back from it.
"""

from __future__ import annotations

import pytest

from basstler.locations import PluginLocation, ProjectLocation
from basstler.plan.exceptions import UnknownGoalError, UnresolvedGoalReferenceError
from basstler.plan.goal import Goal, GoalStore
from basstler.plan.goal_command import (
    GoalExitCode,
    read_path,
    set_goal,
    summary_lines,
)
from basstler.plan.goal_path import GoalPath
from basstler.plan.dependencies import PlanDirectory

from ..constants.paths import DatasetLocation
from ..personal_notes.test_branch import published_file
from ..recorded_pull_requests import RecordedPullRequestSource
from ..scratch_repository import ScratchRepository

# %% the notes branch

STORED_GOAL_FILE = next(
    (DatasetLocation.GOAL_PLANS / ProjectLocation.PLAN_GOALS.name).iterdir()
)
"""
The goal the notes branch starts with.
"""

STORED_GOAL = Goal.from_yaml(STORED_GOAL_FILE.read_text())
"""
That goal, read.
"""


@pytest.fixture
def goal_repository(
    scratch_repository: ScratchRepository, monkeypatch: pytest.MonkeyPatch
) -> ScratchRepository:
    """
    :return: A scratch repository, entered, whose notes branch carries the dataset's
        plans and its goal.
    """
    scratch_repository.install_hook_scripts(
        PluginLocation.PERSONAL_NOTES_CONFIGURATION_SCRIPT.name
    )
    scratch_repository.write("README.md", "scratch repo\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.publish_notes_branch(
        {
            ProjectLocation.PLANS
            / file.relative_to(DatasetLocation.GOAL_PLANS): file.read_text()
            for file in sorted(DatasetLocation.GOAL_PLANS.rglob("*.yaml"))
        }
    )
    scratch_repository.resolve_notes_remote_to()
    monkeypatch.chdir(scratch_repository.project_root)
    return scratch_repository


# %% reading


class TestReadingAGoalsPath:
    """
    A path is computed from the goal and the plans the notes branch holds.
    """

    def test_the_path_matches_the_one_computed_from_the_same_files(
        self, goal_repository: ScratchRepository
    ):
        """
        Reading through the notes branch changes nothing about the path.
        """
        path = read_path(
            STORED_GOAL.identifier,
            goal_repository.project_root,
            RecordedPullRequestSource(),
        )

        assert (
            path.report()
            == GoalPath.compute(
                STORED_GOAL,
                PlanDirectory(DatasetLocation.GOAL_PLANS),
                RecordedPullRequestSource(),
            ).report()
        )

    def test_a_goal_the_branch_does_not_hold_is_refused(
        self, goal_repository: ScratchRepository
    ):
        """
        The refusal names the goals that do exist.
        """
        with pytest.raises(UnknownGoalError) as refusal:
            read_path(
                "no-such-goal",
                goal_repository.project_root,
                RecordedPullRequestSource(),
            )

        assert refusal.value.known_identifiers == (STORED_GOAL.identifier,)


# %% saving


class TestSavingAGoal:
    """
    A goal is pushed to the notes remote only when every target names a plan item.
    """

    def test_a_goal_with_existing_targets_is_pushed(
        self, goal_repository: ScratchRepository
    ):
        """
        The saved goal reads back from the notes remote as it was given.
        """
        saved = Goal(
            identifier="first-target-only",
            title="The first target is reached",
            targets=STORED_GOAL.targets[:1],
        )

        status = set_goal(saved.identifier, saved.title, saved.targets)

        assert (
            status,
            Goal.from_yaml(
                published_file(goal_repository, GoalStore.goal_path(saved.identifier))
            ),
        ) == (GoalExitCode.SUCCESS, saved)

    def test_a_goal_with_a_target_naming_no_item_is_not_pushed(
        self, goal_repository: ScratchRepository
    ):
        """
        A refused goal leaves the notes remote without its file.
        """
        with pytest.raises(UnresolvedGoalReferenceError):
            set_goal("unreachable", "Nothing reaches this", ["review-triage/no-item"])

        assert (
            published_file(goal_repository, GoalStore.goal_path("unreachable")) is None
        )


# %% summarizing


class TestSummarizingGoals:
    """
    Each goal is summarized on one line, whether or not its path can be computed.
    """

    def test_a_goal_is_summarized_by_its_paths_own_line(self):
        """
        A goal whose references resolve reads as its path summarizes itself.
        """
        plan_directory = PlanDirectory(DatasetLocation.GOAL_PLANS)
        path = GoalPath.compute(
            STORED_GOAL,
            PlanDirectory(DatasetLocation.GOAL_PLANS),
            RecordedPullRequestSource(),
        )
        assert summary_lines(
            [STORED_GOAL], plan_directory, RecordedPullRequestSource()
        ) == [path.summary_line]

    def test_the_line_counts_the_steps_and_names_the_next_command(self):
        """
        The line carries the finished and total step counts and the next command.
        """
        path = GoalPath.compute(
            STORED_GOAL,
            PlanDirectory(DatasetLocation.GOAL_PLANS),
            RecordedPullRequestSource(),
        )
        progress = f"{len(path.finished_steps)}/{len(path.steps)} steps finished"
        assert path.summary_line.startswith(f"{STORED_GOAL.identifier}: {progress}")
        assert f"next: {path.next_step.action.command}" in path.summary_line

    def test_a_goal_naming_no_item_is_reported_not_raised(self):
        """
        A goal whose target resolves to nothing gets a line saying so.
        """
        goal = Goal(identifier="lost", title="Lost", targets=["no-plan/no-item"])
        (line,) = summary_lines(
            [goal],
            PlanDirectory(DatasetLocation.GOAL_PLANS),
            RecordedPullRequestSource(),
        )
        unresolved = UnresolvedGoalReferenceError(
            goal.identifier, goal.targets[0], "the goal's targets"
        )
        assert line == f"{goal.identifier}: no path - {unresolved.error_message()}"
