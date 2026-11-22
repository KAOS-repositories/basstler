"""
The plans, goals and pull requests test_pushes_done_dependencies.py and the plan site's goal page tests share.
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
    DependencyReference,
    DependencyResolver,
    PlanDirectory,
)
from basstler.plan.goal import Goal
from basstler.plan.goal_path import GoalPath
from basstler.plan.model import (
    ItemStatus,
    Performer,
    PlanDocument,
)
from basstler.plan.structure import Plan
from basstler_testing.fixture_plans import PLAN_UNDER_TEST_ID
from basstler_testing.manifest_builders import manifest_item, minimal_plan
from basstler_testing.recorded_pull_requests import RecordedPullRequestSource
from basstler_testing.plan import done_check_fixtures as test_done_check


BASE = "base"


"""
The draft item whose pushes the dependent waits for.
"""


DEPENDENT = "dependent"


"""
The not-started item that can start once :data:`BASE` takes no more pushes.
"""


BASE_PULL_REQUEST_NUMBER = 7


"""
The number of the base item's pull request.
"""


FINAL_COMMIT = "a" * 40


"""
The commit the base's session recorded as its last push.
"""


LATER_COMMIT = "b" * 40


"""
A commit pushed to the base after its pushes were recorded as done.
"""


GOAL = Goal(
    identifier="dependent-lands",
    title="The dependent lands",
    targets=[f"{PLAN_UNDER_TEST_ID}/{DEPENDENT}"],
)


"""
The goal whose only target is the dependent.
"""


def manifest(
    pushes_done_at: str | None = FINAL_COMMIT,
    dependent_performer: Performer = Performer.SESSION,
) -> dict:
    """
    :param pushes_done_at: The base's recorded last push, or ``None`` for none yet.
    :param dependent_performer: Who carries the dependent out.
    :return: A plan whose dependent waits for the base's pushes to be done.
    """
    owner_fields = {}
    if dependent_performer is Performer.OWNER:
        owner_fields = {
            "performed_by": Performer.OWNER.value,
            "branch": None,
            "recommended_model": None,
        }
    return minimal_plan(
        items=[
            manifest_item(
                BASE,
                status=ItemStatus.IN_PROGRESS.value,
                pull_request_number=BASE_PULL_REQUEST_NUMBER,
                pushes_done_at=pushes_done_at,
            ),
            manifest_item(
                DEPENDENT,
                depends_on=[BASE],
                depends_on_pushes_done=[BASE],
                **owner_fields,
            ),
        ]
    )


def base_pull_request(
    head_commit: str,
) -> dict[PullRequestReference, PullRequestRecord]:
    """
    :param head_commit: The commit the base's draft pull request points at.
    :return: The base's pull request, by reference.
    """
    plan = Plan.from_mapping(manifest())
    reference = PullRequestReference(
        Repository.parse(plan.default_repository), BASE_PULL_REQUEST_NUMBER
    )
    record = PullRequestRecord(
        state=PullRequestState.OPEN, draft=True, head_commit=head_commit
    )
    return {reference: record}


def live_pull_requests(head_commit: str) -> LivePullRequests:
    """
    :return: What a build reads of the base's pull request.
    """
    records = base_pull_request(head_commit)
    return RecordedPullRequestSource(records=records).live_pull_requests_of(records)


def resolver_with(
    head_commit: str, pushes_done_at: str | None = FINAL_COMMIT
) -> DependencyResolver:
    """
    :return: The plan's dependencies, the base's live state classified.
    """
    resolver = DependencyResolver(plan=Plan.from_mapping(manifest(pushes_done_at)))
    resolver.classify_live_states(live_pull_requests(head_commit))
    return resolver


def path_with(
    tmp_path: Path,
    head_commit: str,
    dependent_performer: Performer = Performer.SESSION,
) -> GoalPath:
    """
    :return: The goal's path over the plan written under ``tmp_path``.
    """
    plan_file = tmp_path / PLAN_UNDER_TEST_ID / PlanDocument.MANIFEST
    plan_file.parent.mkdir()
    plan_file.write_text(
        yaml.safe_dump(manifest(dependent_performer=dependent_performer))
    )
    return GoalPath.compute(
        GOAL,
        PlanDirectory(tmp_path),
        RecordedPullRequestSource(records=base_pull_request(head_commit)),
    )


def dependent_step_reference() -> DependencyReference:
    """
    :return: The dependent, named with its plan.
    """
    return DependencyReference(item_identifier=DEPENDENT, plan_id=PLAN_UNDER_TEST_ID)


owner_step_repository = test_done_check.owner_step_repository


"""
The scratch repository whose notes branch carries the owner-step plan.
"""

