"""
The plans, goals and pull requests test_goal_path.py and the plan site's goal page tests share.
"""

from __future__ import annotations
from enum import StrEnum
import pytest
from basstler.github.pull_request_state import PullRequestRecord, PullRequestState
from basstler.github.states import CombinedCheckState
from basstler.github.repository import PullRequestReference, Repository
from basstler.locations import ProjectLocation
from basstler.plan.dependencies import DependencyReference, PlanDirectory
from basstler.plan.goal import Goal
from basstler.plan.goal_path import (
    GoalPath,
    PathStep,
)
from basstler.plan.structure import Item, Plan
from basstler_testing.constants.paths import DatasetLocation
from basstler_testing.recorded_pull_requests import RecordedPullRequestSource


class GoalPlanId(StrEnum):
    """
    The plans the goal's path runs through.
    """

    REVIEW_TRIAGE = "review-triage"
    """
    The plan holding the goal's targets.
    """

    PACKAGES = "basstler-packages"
    """
    The plan one target depends into.
    """


class StepId(StrEnum):
    """
    The items the tests single out, each for the state its plan records it in.
    """

    NOT_STARTED_BEHIND_DRAFTS = "rule-fix-triage"
    """
    Not started, depending on two items whose pull requests are drafts.
    """

    IN_PROGRESS = "move-triage"
    """
    In progress, depending on nothing.
    """

    BEHIND_ANOTHER_PLAN = "action-plan-triage"
    """
    A target depending on :attr:`IN_ANOTHER_PLAN`.
    """

    IN_ANOTHER_PLAN = "uv-workspace"
    """
    In :attr:`GoalPlanId.PACKAGES`.
    """

    STACKED_WITH_PULL_REQUEST = "actions-marking"
    """
    In progress with a pull request, depending on an item that has one too.
    """

    IN_PROGRESS_WITH_BLOCKER = "viewed-marking-workflow"
    """
    In progress with a pull request, its plan recording a blocker.
    """

    OUTSIDE_THE_PATH = "pypi-release"
    """
    In :attr:`GoalPlanId.PACKAGES`, which no target depends on.
    """


GOAL = Goal.from_yaml(
    (
        DatasetLocation.GOAL_PLANS
        / ProjectLocation.PLAN_GOALS.name
        / "mechanical-files-viewed.yaml"
    ).read_text(encoding="utf-8")
)


"""
The goal every path is computed for.
"""


def reference_of(
    item_identifier: str, plan_id: str = GoalPlanId.REVIEW_TRIAGE
) -> DependencyReference:
    """
    :param item_identifier: An item's id.
    :param plan_id: The plan holding it.
    :return: The reference a path names that item by.
    """
    return DependencyReference(item_identifier=item_identifier, plan_id=plan_id)


@pytest.fixture
def plan_directory() -> PlanDirectory:
    """
    :return: The plans the goal spans, read afresh.
    """
    return PlanDirectory(DatasetLocation.GOAL_PLANS)


def pull_request_reference_of(plan: Plan, item: Item) -> PullRequestReference:
    """
    :param plan: The plan holding the item.
    :param item: An item with a pull request.
    :return: That pull request.
    """
    return PullRequestReference(
        Repository.parse(item.repository or plan.default_repository),
        item.pull_request_number,
    )


def recorded_pull_requests(
    draft: bool,
    merged_items: frozenset[str] = frozenset(),
    failing_items: frozenset[str] = frozenset(),
) -> RecordedPullRequestSource:
    """
    :param draft: Whether every open pull request is a draft.
    :param merged_items: The ids of the items whose pull requests have merged.
    :param failing_items: The ids of the items whose pull requests' checks failed.
    :return: A pull request for every item of the spanned plans that names one.
    """
    directory = PlanDirectory(DatasetLocation.GOAL_PLANS)
    records = {}
    for plan in map(directory.plan, GoalPlanId):
        for item in plan.items:
            if item.pull_request_number is None:
                continue
            merged = item.identifier in merged_items
            records[pull_request_reference_of(plan, item)] = PullRequestRecord(
                state=PullRequestState.CLOSED if merged else PullRequestState.OPEN,
                draft=draft and not merged,
                merged_at="2026-11-15T00:00:00+00:00" if merged else None,
                check_state=CombinedCheckState.FAILURE
                if item.identifier in failing_items
                else CombinedCheckState.SUCCESS,
            )
    return RecordedPullRequestSource(records=records)


def path_with(
    plan_directory: PlanDirectory, pull_requests: RecordedPullRequestSource
) -> GoalPath:
    """
    :return: The goal's path over the plans, with those pull requests.
    """
    return GoalPath.compute(GOAL, plan_directory, pull_requests)


def step_of(path: GoalPath, reference: DependencyReference) -> PathStep:
    """
    :return: The path's step for the referenced item.
    """
    (step,) = [step for step in path.steps if step.reference == reference]
    return step

