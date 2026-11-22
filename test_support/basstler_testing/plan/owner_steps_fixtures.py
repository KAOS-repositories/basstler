"""
The plans, goals and pull requests test_owner_steps.py and the plan site's goal page tests share.
"""

from __future__ import annotations
from enum import StrEnum
import pytest
from basstler.github.pull_request_state import PullRequestRecord, PullRequestState
from basstler.github.repository import PullRequestReference, Repository
from basstler.locations import ProjectLocation
from basstler.plan.dependencies import DependencyReference, PlanDirectory
from basstler.plan.goal import Goal
from basstler.plan.goal_path import GoalPath
from basstler.plan.structure import Item
from basstler_testing.constants.paths import DatasetLocation
from basstler_testing.recorded_pull_requests import RecordedPullRequestSource


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
    ).read_text(encoding="utf-8")
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

