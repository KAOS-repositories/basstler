"""
Tests for dependencies whose pushes must be done: how a manifest declares one, what it
holds back, and how an item records that its pushes are done.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from basstler.github.pull_request_state import (
    LivePullRequests,
    PullRequestRecord,
    PullRequestState,
)
from basstler.github.repository import PullRequestReference, Repository
from basstler.plan.check_dependency_readiness import DependencyReadiness
from basstler.plan.dependencies import (
    DependencyReference,
    DependencyResolver,
    PlanDirectory,
)
from basstler.plan.exceptions import (
    DependsOnPushesDoneNotDependedOn,
    InvalidPushesDoneAt,
    PlanValidationError,
    StepReferenceWithoutPlanError,
)
from basstler.plan.goal import Goal
from basstler.plan.goal_command import GoalExitCode, record_pushes_done
from basstler.plan.goal_path import GoalPath
from basstler.plan.item_action import StartNowAction
from basstler.plan.model import DependencyRelease, ItemStatus, ManifestKey, PlanDocument
from basstler.plan.structure import Plan
from basstler.plan.validation import PlanValidator

from ..fixture_plans import PLAN_UNDER_TEST_ID
from ..manifest_builders import manifest_item, minimal_plan
from ..recorded_pull_requests import RecordedPullRequestSource
from ..scratch_repository import ScratchRepository
from . import test_done_check
from .test_done_check import published_manifest
from .test_goal_path import step_of
from .test_owner_steps import StepId, reference_of

# %% a plan whose second item waits for the first one's pushes

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


def manifest(pushes_done_at: str | None = FINAL_COMMIT) -> dict:
    """
    :param pushes_done_at: The base's recorded last push, or ``None`` for none yet.
    :return: A plan whose dependent waits for the base's pushes to be done.
    """
    return minimal_plan(
        items=[
            manifest_item(
                BASE,
                status=ItemStatus.IN_PROGRESS.value,
                pull_request_number=BASE_PULL_REQUEST_NUMBER,
                pushes_done_at=pushes_done_at,
            ),
            manifest_item(DEPENDENT, depends_on=[BASE], depends_on_pushes_done=[BASE]),
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


def path_with(tmp_path: Path, head_commit: str) -> GoalPath:
    """
    :return: The goal's path over the plan written under ``tmp_path``.
    """
    plan_file = tmp_path / PLAN_UNDER_TEST_ID / PlanDocument.MANIFEST
    plan_file.parent.mkdir()
    plan_file.write_text(yaml.safe_dump(manifest()))
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


# %% declaring one


class TestDeclaringAPushesDoneDependency:
    """
    ``depends_on_pushes_done`` names the entries of ``depends_on`` whose pushes must be
    done, and ``pushes_done_at`` records an item's last push.
    """

    def test_an_item_carries_the_entries_whose_pushes_it_waits_for(self):
        """
        The manifest's list is read onto the item.
        """
        dependent = Plan.from_mapping(manifest()).items_by_identifier[DEPENDENT]
        assert dependent.depends_on_pushes_done == [BASE]

    def test_an_item_carries_its_recorded_last_push(self):
        """
        The recorded commit is read onto the item.
        """
        base = Plan.from_mapping(manifest()).items_by_identifier[BASE]
        assert base.pushes_done_at == FINAL_COMMIT

    def test_each_entry_names_what_the_dependent_waits_for(self):
        """
        An entry waits for pushes done, merged, or by default ready for review.
        """
        dependent = Plan.from_mapping(manifest()).items_by_identifier[DEPENDENT]
        assert dependent.release_needed_from(BASE) is DependencyRelease.PUSHES_DONE

    def test_an_entry_missing_from_depends_on_is_refused(self):
        """
        An entry the item does not depend on is a validation problem.
        """
        content = manifest()
        content[ManifestKey.ITEMS.key][1][ManifestKey.DEPENDS_ON.key] = []
        with pytest.raises(PlanValidationError) as error:
            PlanValidator(content).validate()
        assert [type(problem) for problem in error.value.problems] == [
            DependsOnPushesDoneNotDependedOn
        ]

    def test_an_entry_also_needed_merged_is_refused(self):
        """
        An entry waits for one release only, so it cannot be in both lists.
        """
        content = manifest()
        content[ManifestKey.ITEMS.key][1][ManifestKey.DEPENDS_ON_MERGED.key] = [BASE]
        with pytest.raises(PlanValidationError) as error:
            PlanValidator(content).validate()
        assert [type(problem) for problem in error.value.problems] == [
            DependsOnPushesDoneNotDependedOn
        ]

    def test_a_last_push_that_is_not_a_commit_is_refused(self):
        """
        ``pushes_done_at`` holds a full commit id.
        """
        with pytest.raises(PlanValidationError) as error:
            PlanValidator(manifest(pushes_done_at="main")).validate()
        assert [type(problem) for problem in error.value.problems] == [
            InvalidPushesDoneAt
        ]

    def test_the_plan_under_test_is_valid(self):
        """
        A recorded last push and a dependent waiting on it pass validation.
        """
        PlanValidator(manifest()).validate()


# %% what it holds back


class TestWhatAPushesDoneDependencyHoldsBack:
    """
    A dependency whose pushes are done releases its dependent while still a draft, and
    only while its pull request still points at the recorded commit.
    """

    def test_a_draft_at_its_last_push_releases_the_dependent(self):
        """
        Still a draft, the base releases the dependent once its pushes are done.
        """
        resolver = resolver_with(head_commit=FINAL_COMMIT)
        dependent = resolver.plan.items_by_identifier[DEPENDENT]
        assert not resolver.resolve(BASE).is_ready_to_unblock_dependents()
        assert resolver.dependencies_are_ready(dependent)

    def test_a_push_after_the_recorded_one_holds_the_dependent_back(self):
        """
        A later push resumes the base's pushes, so the dependent waits again.
        """
        resolver = resolver_with(head_commit=LATER_COMMIT)
        dependent = resolver.plan.items_by_identifier[DEPENDENT]
        assert not resolver.dependencies_are_ready(dependent)

    def test_no_recorded_last_push_holds_the_dependent_back(self):
        """
        Until the base records its last push the dependent waits.
        """
        resolver = resolver_with(head_commit=FINAL_COMMIT, pushes_done_at=None)
        dependent = resolver.plan.items_by_identifier[DEPENDENT]
        assert not resolver.dependencies_are_ready(dependent)

    @pytest.mark.parametrize(
        ("head_commit", "is_ready"), [(FINAL_COMMIT, True), (LATER_COMMIT, False)]
    )
    def test_the_readiness_check_reports_the_pushes(
        self, head_commit: str, is_ready: bool
    ):
        """
        The dependency is reported ready exactly while its head is the last push.
        """
        plan = Plan.from_mapping(manifest())
        (readiness,) = DependencyReadiness.of_item(
            plan, DEPENDENT, live_pull_requests(head_commit)
        )
        assert readiness.release is DependencyRelease.PUSHES_DONE
        assert readiness.is_ready is is_ready

    def test_a_path_keeps_the_dependent_waiting_for_the_pushes(self, tmp_path: Path):
        """
        On a goal's path the dependent awaits the base, named as needing its pushes.
        """
        base = DependencyReference(item_identifier=BASE, plan_id=PLAN_UNDER_TEST_ID)
        path = path_with(tmp_path, head_commit=LATER_COMMIT)
        step = step_of(path, dependent_step_reference())
        assert step.awaited == (base,)
        assert step.awaited_pushes == (base,)
        assert step.report(path.position_of(step), ()).awaited_pushes == [base.text]

    def test_a_path_starts_the_dependent_at_the_last_push(self, tmp_path: Path):
        """
        While the base's head is its recorded last push the dependent can be started.
        """
        step = step_of(
            path_with(tmp_path, head_commit=FINAL_COMMIT), dependent_step_reference()
        )
        assert step.awaited == ()
        assert isinstance(step.action, StartNowAction)


# %% recording that an item's pushes are done

owner_step_repository = test_done_check.owner_step_repository
"""
The scratch repository whose notes branch carries the owner-step plan.
"""


class TestRecordingThatPushesAreDone:
    """
    ``goal pushes-done`` records an item's last push on the notes remote.
    """

    def test_the_last_push_is_recorded_on_the_item(
        self, owner_step_repository: ScratchRepository
    ):
        """
        The named item carries the commit its pushes ended at.
        """
        step = reference_of(StepId.BEFORE_THE_OWNER)
        assert record_pushes_done(step.text, FINAL_COMMIT) is GoalExitCode.SUCCESS
        item = published_manifest(owner_step_repository).item_named(
            StepId.BEFORE_THE_OWNER
        )
        assert item.content[ManifestKey.PUSHES_DONE_AT.key] == FINAL_COMMIT

    def test_a_step_named_without_its_plan_is_refused(
        self, owner_step_repository: ScratchRepository
    ):
        """
        A bare item id names no step.
        """
        with pytest.raises(StepReferenceWithoutPlanError):
            record_pushes_done(StepId.BEFORE_THE_OWNER, FINAL_COMMIT)
