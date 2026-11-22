"""
The plans, goals and pull requests test_merged_dependencies.py and the plan site's goal page tests share.
"""

from __future__ import annotations
from pathlib import Path
import yaml
from basstler.github.pull_request_state import (
    LivePullRequests,
    PullRequestRecord,
    PullRequestState,
)
from basstler.github.repository import PullRequestReference, Repository
from basstler.plan.dependencies import (
    DependencyResolver,
    PlanDirectory,
)
from basstler.plan.goal import Goal
from basstler.plan.goal_path import GoalPath
from basstler.plan.model import ItemStatus, PlanDocument
from basstler.plan.structure import Plan
from basstler_testing.fixture_plans import PLAN_UNDER_TEST_ID
from basstler_testing.manifest_builders import manifest_item, minimal_plan
from basstler_testing.recorded_pull_requests import RecordedPullRequestSource


BASE = "base"


"""
The item the dependent needs merged.
"""


DEPENDENT = "dependent"


"""
The not-started item that builds on :data:`BASE` only once it has merged.
"""


BASE_PULL_REQUEST_NUMBER = 7


"""
The number of the base item's pull request.
"""


GOAL = Goal(
    identifier="dependent-lands",
    title="The dependent lands",
    targets=[f"{PLAN_UNDER_TEST_ID}/{DEPENDENT}"],
)


"""
The goal whose only target is the dependent.
"""


def manifest() -> dict:
    """
    :return: A plan whose dependent lists the base in both dependency lists.
    """
    return minimal_plan(
        items=[
            manifest_item(
                BASE,
                status=ItemStatus.IN_PROGRESS.value,
                pull_request_number=BASE_PULL_REQUEST_NUMBER,
            ),
            manifest_item(DEPENDENT, depends_on=[BASE], depends_on_merged=[BASE]),
        ]
    )


def base_pull_request(merged: bool) -> dict[PullRequestReference, PullRequestRecord]:
    """
    :param merged: Whether the base's pull request has merged; out of draft otherwise.
    :return: The base's pull request, by reference.
    """
    plan = Plan.from_mapping(manifest())
    reference = PullRequestReference(
        Repository.parse(plan.default_repository), BASE_PULL_REQUEST_NUMBER
    )
    record = PullRequestRecord(
        state=PullRequestState.CLOSED if merged else PullRequestState.OPEN,
        draft=False,
        merged_at="2026-11-15T00:00:00+00:00" if merged else None,
    )
    return {reference: record}


def live_pull_requests(merged: bool) -> LivePullRequests:
    """
    :return: What a build reads of the base's pull request.
    """
    records = base_pull_request(merged)
    return RecordedPullRequestSource(records=records).live_pull_requests_of(records)


def resolver_with(merged: bool) -> DependencyResolver:
    """
    :return: The plan's dependencies, the base's live state classified.
    """
    resolver = DependencyResolver(plan=Plan.from_mapping(manifest()))
    resolver.classify_live_states(live_pull_requests(merged))
    return resolver


def path_with(tmp_path: Path, merged: bool) -> GoalPath:
    """
    :return: The goal's path over the plan written under ``tmp_path``.
    """
    plan_file = tmp_path / PLAN_UNDER_TEST_ID / PlanDocument.MANIFEST
    plan_file.parent.mkdir()
    plan_file.write_text(yaml.safe_dump(manifest()))
    return GoalPath.compute(
        GOAL,
        PlanDirectory(tmp_path),
        RecordedPullRequestSource(records=base_pull_request(merged)),
    )

