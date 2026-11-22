"""
Tests for dependencies whose pushes must be done: how a manifest declares one, what it
holds back, and how an item records that its pushes are done.
"""

from __future__ import annotations
from pathlib import Path
import pytest
from basstler.plan.check_dependency_readiness import DependencyReadiness
from basstler.plan.dependencies import (
    DependencyReference,
)
from basstler.plan.exceptions import (
    DependsOnPushesDoneNotDependedOn,
    InvalidPushesDoneAt,
    PlanValidationError,
    StepReferenceWithoutPlanError,
)
from basstler.plan.goal_command import GoalExitCode, record_pushes_done
from basstler.plan.item_action import StartNowAction
from basstler.plan.model import (
    DependencyRelease,
    ManifestKey,
    Performer,
)
from basstler.plan.structure import Plan
from basstler.plan.validation import PlanValidator
from basstler_testing.fixture_plans import PLAN_UNDER_TEST_ID
from basstler_testing.scratch_repository import ScratchRepository
from basstler_testing.plan.done_check_fixtures import published_manifest
from basstler_testing.plan.goal_path_fixtures import step_of
from basstler_testing.plan.owner_steps_fixtures import StepId, reference_of
from basstler_testing.plan.pushes_done_dependencies_fixtures import (
    BASE,
    DEPENDENT,
    FINAL_COMMIT,
    LATER_COMMIT,
    manifest,
    live_pull_requests,
    resolver_with,
    path_with,
    dependent_step_reference,
)
from basstler_testing.plan.done_check_fixtures import owner_step_repository  # noqa: F401 - a fixture


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


class TestWhatTheOwnerIsToldOfAPushesDoneDependency:
    """
    The owner's review of a draft does not release what waits for its pushes, and an
    owner step that waits for them says so.
    """

    def test_reviewing_the_draft_is_not_said_to_release_the_dependent(
        self, tmp_path: Path
    ):
        """
        Marking the base ready leaves the dependent waiting for the base's pushes.
        """
        path = path_with(tmp_path, head_commit=LATER_COMMIT)
        base = step_of(
            path, DependencyReference(item_identifier=BASE, plan_id=PLAN_UNDER_TEST_ID)
        )
        assert path.references_released_by(base) == ()

    def test_an_owner_step_names_the_pushes_it_waits_for(self, tmp_path: Path):
        """
        The owner's step comes after the base's pushes are done, in those words.
        """
        path = path_with(
            tmp_path, head_commit=LATER_COMMIT, dependent_performer=Performer.OWNER
        )
        base = DependencyReference(item_identifier=BASE, plan_id=PLAN_UNDER_TEST_ID)
        move = step_of(path, dependent_step_reference()).owner_move
        assert move.description == (
            f"{move.summary} after {base.text} "
            f"{move.waiting_phrase_of(DependencyRelease.PUSHES_DONE)}"
        )


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

