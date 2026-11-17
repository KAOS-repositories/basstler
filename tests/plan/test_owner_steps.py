"""
Tests for the steps a plan's owner performs: how a manifest declares one, and how a goal's
path offers it.
"""

from __future__ import annotations

from enum import StrEnum

import pytest
import yaml

from basstler.github.pull_request_state import PullRequestRecord, PullRequestState
from basstler.github.repository import PullRequestReference, Repository
from basstler.locations import ProjectLocation
from basstler.plan.dependencies import DependencyReference, PlanDirectory
from basstler.plan.exceptions import (
    InvalidCommands,
    PlanValidationError,
    UnknownPerformer,
)
from basstler.plan.goal import Goal
from basstler.plan.goal_path import GoalPath, OwnerPerformedStep
from basstler.plan.item_action import ItemAction, StartNowAction
from basstler.plan.model import ItemStatus, ManifestKey, Performer
from basstler.plan.structure import Item
from basstler.plan.validation import PlanValidator

from ..constants.paths import DatasetLocation
from ..manifest_builders import manifest_item, minimal_plan
from ..recorded_pull_requests import RecordedPullRequestSource
from .test_goal_path import step_of

# %% the plan with a step its owner performs

PLAN_ID = "site-setup"
"""
The plan the goal's path runs through.
"""


class StepId(StrEnum):
    """
    The plan's items, each named for its part in the path.
    """

    BEFORE_THE_OWNER = "build-workflow"
    """
    A session's item with a pull request, which the owner's step depends on.
    """

    OWNER = "store-token"
    """
    The step the owner performs.
    """

    AFTER_THE_OWNER = "verify-site"
    """
    A session's item depending on the owner's step.
    """


GOAL = Goal.from_yaml(
    (
        DatasetLocation.OWNER_STEP_PLANS
        / ProjectLocation.PLAN_GOALS.name
        / "site-published.yaml"
    ).read_text()
)
"""
The goal behind the owner's step.
"""


def reference_of(step: StepId) -> DependencyReference:
    """
    :return: The reference a path names that item by.
    """
    return DependencyReference(item_identifier=step, plan_id=PLAN_ID)


@pytest.fixture
def plan_directory() -> PlanDirectory:
    """
    :return: The plan, read afresh.
    """
    return PlanDirectory(DatasetLocation.OWNER_STEP_PLANS)


def owner_item(plan_directory: PlanDirectory) -> Item:
    """
    :return: The item the owner performs.
    """
    return plan_directory.plan(PLAN_ID).items_by_identifier[StepId.OWNER]


def path_with(plan_directory: PlanDirectory, draft: bool) -> GoalPath:
    """
    :param draft: Whether the pull request before the owner's step is a draft.
    :return: The goal's path.
    """
    plan = plan_directory.plan(PLAN_ID)
    before = plan.items_by_identifier[StepId.BEFORE_THE_OWNER]
    reference = PullRequestReference(
        Repository.parse(plan.default_repository), before.pull_request_number
    )
    record = PullRequestRecord(state=PullRequestState.OPEN, draft=draft, merged_at=None)
    return GoalPath.compute(
        GOAL, plan_directory, RecordedPullRequestSource(records={reference: record})
    )


# %% declaring an owner's step


class TestDeclaringAnOwnersStep:
    """
    A manifest says who performs an item and the commands that carry it out.
    """

    def test_an_item_is_performed_by_a_session_unless_it_says_otherwise(self):
        """
        An entry naming no performer is a session's.
        """
        assert Item.from_mapping(manifest_item("a")).performed_by is Performer.SESSION

    def test_an_item_carries_its_performer_and_commands(
        self, plan_directory: PlanDirectory
    ):
        """
        The manifest's performer and commands are read onto the item.
        """
        item = owner_item(plan_directory)
        assert item.performed_by is Performer.OWNER
        assert item.commands == [
            "gh secret set PLAN_SITE_TOKEN --repo example/site",
            "gh workflow run plan-site.yml --repo example/site",
        ]

    def test_an_unknown_performer_is_refused(self):
        """
        A performer that is neither the owner nor a session is a validation problem.
        """
        items = [manifest_item("a", performed_by="reviewer")]
        with pytest.raises(PlanValidationError) as error:
            PlanValidator(minimal_plan(items=items)).validate()
        assert [type(problem) for problem in error.value.problems] == [UnknownPerformer]

    def test_commands_that_are_not_a_list_are_refused(self):
        """
        A single command written as a string is a validation problem.
        """
        items = [manifest_item("a", performed_by=Performer.OWNER, commands="gh x")]
        with pytest.raises(PlanValidationError) as error:
            PlanValidator(minimal_plan(items=items)).validate()
        assert [type(problem) for problem in error.value.problems] == [InvalidCommands]

    def test_a_new_owners_step_needs_no_recommended_model(self):
        """
        No session runs an owner's step, so a save asks it for no model.
        """
        item = manifest_item("a", performed_by=Performer.OWNER, recommended_model=None)
        PlanValidator(
            minimal_plan(items=[item]), saved_item_identifiers=frozenset()
        ).validate()

    def test_the_dataset_plan_is_valid(self, plan_directory: PlanDirectory):
        """
        The plan the path tests read passes validation.
        """
        manifest = (
            DatasetLocation.OWNER_STEP_PLANS / PLAN_ID / "plan.yaml"
        ).read_text()
        assert ManifestKey.PERFORMED_BY.key in manifest
        PlanValidator(yaml.safe_load(manifest)).validate()


# %% an owner's step on a path


class TestAnOwnersStepOnAPath:
    """
    A path offers an owner's step to the owner, never to a session.
    """

    def test_no_session_action_carries_it_out(self, plan_directory: PlanDirectory):
        """
        An owner's step has no skill command, whether or not its dependencies are ready.
        """
        action = ItemAction.from_item_state(
            PLAN_ID, owner_item(plan_directory), dependencies_are_ready=True
        )
        assert action is None

    def test_it_waits_for_the_draft_it_depends_on(self, plan_directory: PlanDirectory):
        """
        While its dependency is a draft, the owner's step names it as what it comes after.
        """
        path = path_with(plan_directory, draft=True)
        step = step_of(path, reference_of(StepId.OWNER))
        item = owner_item(plan_directory)
        assert step.owner_move == OwnerPerformedStep(
            title=item.title,
            step_commands=tuple(item.commands),
            after=(reference_of(StepId.BEFORE_THE_OWNER),),
        )
        assert step not in path.owner_steps

    def test_it_is_the_owners_now_once_its_dependency_is_ready(
        self, plan_directory: PlanDirectory
    ):
        """
        Once nothing is awaited the step is among those the owner can act on.
        """
        path = path_with(plan_directory, draft=False)
        step = step_of(path, reference_of(StepId.OWNER))
        assert step.owner_move.after == ()
        assert step in path.owner_steps

    def test_what_depends_on_it_waits_until_it_is_done(
        self, plan_directory: PlanDirectory
    ):
        """
        A step behind the owner's has no action until the owner's step is done.
        """
        waiting = step_of(
            path_with(plan_directory, draft=False),
            reference_of(StepId.AFTER_THE_OWNER),
        )
        assert waiting.awaited == (reference_of(StepId.OWNER),)
        assert waiting.action is None

    def test_what_depends_on_it_starts_once_it_is_done(self):
        """
        Marking the owner's step done releases the step behind it.
        """
        plan_directory = PlanDirectory(DatasetLocation.OWNER_STEP_PLANS)
        owner_item(plan_directory).status = ItemStatus.DONE
        released = step_of(
            path_with(plan_directory, draft=False),
            reference_of(StepId.AFTER_THE_OWNER),
        )
        assert isinstance(released.action, StartNowAction)

    def test_the_report_carries_its_commands(self, plan_directory: PlanDirectory):
        """
        A reported owner's step lists the commands the owner runs.
        """
        path = path_with(plan_directory, draft=False)
        step = step_of(path, reference_of(StepId.OWNER))
        reported = step.report(
            path.position_of(step), path.references_released_by(step)
        )
        assert reported.owner_move == step.owner_move.description
        assert reported.owner_commands == owner_item(plan_directory).commands

    def test_the_printed_path_lists_its_commands(self, plan_directory: PlanDirectory):
        """
        Every command of the owner's step is a line of the printed path.
        """
        printed = path_with(plan_directory, draft=False).render().splitlines()
        for command in owner_item(plan_directory).commands:
            assert f"        {command}" in printed
