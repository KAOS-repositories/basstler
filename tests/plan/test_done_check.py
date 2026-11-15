"""
Tests for basstler.plan.done_check and the ``basstler goal`` commands that record a step
as done.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import pytest
import yaml

from basstler.locations import PluginLocation, ProjectLocation
from basstler.plan.dependencies import PlanDirectory
from basstler.plan.done_check import (
    BasstlerCommandRunner,
    DoneChecker,
    DoneCheckOutcome,
    FinishedStep,
)
from basstler.plan.exceptions import (
    InvalidCommands,
    PlanValidationError,
    StepReferenceWithoutPlanError,
)
from basstler.plan.goal_command import GoalExitCode, check_steps, mark_done
from basstler.plan.goal_path import GoalCommandName
from basstler.plan.model import ItemStatus, PlanDocument, PlanManifest
from basstler.plan.validation import PlanValidator

from ..constants.paths import DatasetLocation
from ..manifest_builders import manifest_item, minimal_plan
from ..personal_notes.test_branch import published_file
from ..scratch_repository import ScratchRepository
from .test_goal_path import step_of
from .test_owner_steps import GOAL, PLAN_ID, StepId, owner_item, path_with, reference_of

# %% a runner that answers from a record


@dataclass(frozen=True)
class RecordedExitStatus(BasstlerCommandRunner):
    """
    Answers every command with one fixed exit status, noting what it was asked to run.
    """

    exit_status: int = 0
    """
    The status every command exits with.
    """

    commands_run: list[list[str]] = field(default_factory=list)
    """
    The arguments of every command asked for, in order.
    """

    def exit_status_of(self, arguments: list[str]) -> int:
        self.commands_run.append(arguments)
        return self.exit_status


@pytest.fixture
def plan_directory() -> PlanDirectory:
    """
    :return: The plan whose owner's step carries a done check, read afresh.
    """
    return PlanDirectory(DatasetLocation.OWNER_STEP_PLANS)


@pytest.fixture
def owner_step_repository(
    scratch_repository: ScratchRepository, monkeypatch: pytest.MonkeyPatch
) -> ScratchRepository:
    """
    :return: A scratch repository, entered, whose notes branch carries the plan.
    """
    scratch_repository.install_hook_scripts(
        PluginLocation.PERSONAL_NOTES_CONFIGURATION_SCRIPT.name,
        PluginLocation.PLAN_SAVING_SCRIPT.name,
    )
    scratch_repository.install_package()
    scratch_repository.write("README.md", "scratch repo\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.publish_notes_branch(
        {
            ProjectLocation.PLANS
            / file.relative_to(DatasetLocation.OWNER_STEP_PLANS): file.read_text()
            for file in sorted(DatasetLocation.OWNER_STEP_PLANS.rglob("*"))
            if file.is_file()
        }
    )
    scratch_repository.resolve_notes_remote_to()
    scratch_repository.serve_origin_as(
        PlanManifest.from_file(
            DatasetLocation.OWNER_STEP_PLANS / PLAN_ID / PlanDocument.MANIFEST
        ).default_repository
    )
    monkeypatch.chdir(scratch_repository.project_root)
    return scratch_repository


def published_manifest(repository: ScratchRepository) -> PlanManifest:
    """
    :return: The plan as the notes remote holds it.
    """
    return PlanManifest.from_yaml(
        published_file(
            repository,
            PurePosixPath(PlanDocument.MANIFEST.path_within_notes_branch(PLAN_ID)),
        )
    )


def is_recorded_done(repository: ScratchRepository, step: StepId) -> bool:
    """
    :return: Whether the notes remote counts the step's item as landed, which a save
        does by dropping it from the plan.
    """
    manifest = published_manifest(repository)
    remaining = {item.identifier for item in manifest.items}
    return step not in remaining and manifest.landed_item_count == 1


# %% declaring a done check


class TestDeclaringADoneCheck:
    """
    ``done_when`` holds the arguments of the basstler command that proves an item done.
    """

    def test_an_item_carries_its_done_check(self, plan_directory: PlanDirectory):
        """
        The manifest's arguments are read onto the item.
        """
        manifest = yaml.safe_load(
            (DatasetLocation.OWNER_STEP_PLANS / PLAN_ID / "plan.yaml").read_text()
        )
        (declared,) = [
            entry["done_when"] for entry in manifest["items"] if "done_when" in entry
        ]
        assert owner_item(plan_directory).done_when == declared

    def test_a_done_check_that_is_not_a_list_is_refused(self):
        """
        A check written as one string is a validation problem.
        """
        items = [manifest_item("a", done_when="goal path x")]
        with pytest.raises(PlanValidationError) as error:
            PlanValidator(minimal_plan(items=items)).validate()
        assert [type(problem) for problem in error.value.problems] == [InvalidCommands]


# %% which checks run


class TestWhichChecksRun:
    """
    A check runs only for an unfinished step that waits for nothing.
    """

    def test_a_step_waiting_for_nothing_is_checked(
        self, plan_directory: PlanDirectory, tmp_path: Path
    ):
        """
        The step's own arguments are what the runner is asked to run.
        """
        runner = RecordedExitStatus(tmp_path)
        outcomes = DoneChecker(runner).outcomes_of(
            path_with(plan_directory, draft=False)
        )
        assert outcomes == [DoneCheckOutcome(reference_of(StepId.OWNER), 0)]
        assert runner.commands_run == [owner_item(plan_directory).done_when]

    def test_a_step_still_waiting_is_not_checked(
        self, plan_directory: PlanDirectory, tmp_path: Path
    ):
        """
        No check runs while the step's dependency is a draft.
        """
        runner = RecordedExitStatus(tmp_path)
        assert (
            DoneChecker(runner).outcomes_of(path_with(plan_directory, draft=True)) == []
        )
        assert runner.commands_run == []

    def test_a_finished_step_is_not_checked(
        self, plan_directory: PlanDirectory, tmp_path: Path
    ):
        """
        A step already done is left alone.
        """
        owner_item(plan_directory).status = ItemStatus.DONE
        runner = RecordedExitStatus(tmp_path)
        assert (
            DoneChecker(runner).outcomes_of(path_with(plan_directory, draft=False))
            == []
        )

    @pytest.mark.parametrize(("exit_status", "passed"), [(0, True), (1, False)])
    def test_a_check_passes_exactly_when_it_exits_zero(
        self, exit_status: int, passed: bool
    ):
        """
        Only a zero exit status proves the step done.
        """
        outcome = DoneCheckOutcome(reference_of(StepId.OWNER), exit_status)
        assert outcome.passed is passed

    @pytest.mark.parametrize(
        ("arguments", "succeeds"),
        [([GoalCommandName.GROUP, "--help"], True), (["no-such-command"], False)],
    )
    def test_the_runner_reports_how_a_basstler_command_exits(
        self, tmp_path: Path, arguments: list[str], succeeds: bool
    ):
        """
        A command basstler has exits zero, and one it lacks does not.
        """
        exit_status = BasstlerCommandRunner(tmp_path).exit_status_of(arguments)
        assert (exit_status == 0) is succeeds


# %% what closes a step


class TestWhatClosesAStep:
    """
    A path names the command that records each step as done.
    """

    def test_a_step_with_a_done_check_is_closed_by_checking_the_goal(
        self, plan_directory: PlanDirectory
    ):
        """
        The step's closing command checks its goal.
        """
        step = step_of(
            path_with(plan_directory, draft=False), reference_of(StepId.OWNER)
        )
        assert step.closing_command == GoalCommandName.CHECK.invocation(GOAL.identifier)

    def test_an_owners_step_without_a_check_is_closed_by_marking_it(
        self, plan_directory: PlanDirectory
    ):
        """
        With nothing to check, the owner records the step done by naming it.
        """
        owner_item(plan_directory).done_when = []
        reference = reference_of(StepId.OWNER)
        step = step_of(path_with(plan_directory, draft=False), reference)
        assert step.closing_command == GoalCommandName.MARK_DONE.invocation(
            reference.text
        )

    def test_a_sessions_step_has_no_closing_command(
        self, plan_directory: PlanDirectory
    ):
        """
        A step with a pull request is finished by its merge alone.
        """
        step = step_of(
            path_with(plan_directory, draft=False),
            reference_of(StepId.BEFORE_THE_OWNER),
        )
        assert step.closing_command is None

    def test_the_printed_path_names_the_closing_command(
        self, plan_directory: PlanDirectory
    ):
        """
        The owner's step ends with the command that records it.
        """
        path = path_with(plan_directory, draft=False)
        closing = step_of(path, reference_of(StepId.OWNER)).closing_command
        assert f"      then: {closing}" in path.render().splitlines()


# %% recording a step as done


class TestRecordingAStepAsDone:
    """
    A step is set to done on the notes remote by a passing check or its owner's word.
    """

    def test_a_passing_check_marks_the_step_done(
        self, owner_step_repository: ScratchRepository, plan_directory: PlanDirectory
    ):
        """
        After a check that exits zero the notes remote records the step done.
        """
        runner = RecordedExitStatus(owner_step_repository.project_root)
        exit_code = check_steps(
            path_with(plan_directory, draft=False), DoneChecker(runner)
        )
        assert exit_code is GoalExitCode.SUCCESS
        assert is_recorded_done(owner_step_repository, StepId.OWNER)

    def test_a_failing_check_leaves_the_step_as_it_was(
        self, owner_step_repository: ScratchRepository, plan_directory: PlanDirectory
    ):
        """
        After a check that exits non-zero the step keeps its status.
        """
        runner = RecordedExitStatus(owner_step_repository.project_root, exit_status=1)
        exit_code = check_steps(
            path_with(plan_directory, draft=False), DoneChecker(runner)
        )
        assert exit_code is GoalExitCode.STEP_NOT_DONE
        assert (
            published_manifest(owner_step_repository).item_named(StepId.OWNER).status
            is owner_item(plan_directory).status
        )

    def test_the_owner_marks_a_step_done_by_naming_it(
        self, owner_step_repository: ScratchRepository
    ):
        """
        ``mark-done`` records the named step done on the notes remote.
        """
        assert mark_done(reference_of(StepId.OWNER).text) is GoalExitCode.SUCCESS
        assert is_recorded_done(owner_step_repository, StepId.OWNER)

    def test_a_step_named_without_its_plan_is_refused(
        self, owner_step_repository: ScratchRepository
    ):
        """
        A bare item id names no step.
        """
        with pytest.raises(StepReferenceWithoutPlanError):
            mark_done(StepId.OWNER)

    def test_recording_names_the_item_it_sets(self):
        """
        A finished step is the reference it was built from.
        """
        reference = reference_of(StepId.OWNER)
        assert FinishedStep(reference).reference == reference
