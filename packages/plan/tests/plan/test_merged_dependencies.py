"""
Tests for dependencies that must be merged: how a manifest declares one, and what it
holds back until the merge.
"""

from __future__ import annotations
from pathlib import Path
import pytest
from basstler.plan.check_dependency_readiness import DependencyReadiness
from basstler.plan.dependencies import (
    DependencyReference,
)
from basstler.plan.exceptions import DependsOnMergedNotDependedOn, PlanValidationError
from basstler.plan.item_action import StartNowAction
from basstler.plan.model import DependencyRelease, ManifestKey
from basstler.plan.structure import Plan
from basstler.plan.validation import PlanValidator
from basstler_testing.fixture_plans import PLAN_UNDER_TEST_ID
from basstler_testing.plan.goal_path_fixtures import step_of
from basstler_testing.plan.merged_dependencies_fixtures import (
    BASE,
    DEPENDENT,
    manifest,
    live_pull_requests,
    resolver_with,
    path_with,
)


class TestDeclaringAMergedDependency:
    """
    ``depends_on_merged`` names the entries of ``depends_on`` that must be merged.
    """

    def test_an_item_carries_the_entries_it_needs_merged(self):
        """
        The manifest's list is read onto the item.
        """
        dependent = Plan.from_mapping(manifest()).items_by_identifier[DEPENDENT]
        assert dependent.depends_on_merged == [BASE]

    def test_an_entry_missing_from_depends_on_is_refused(self):
        """
        An entry the item does not depend on is a validation problem.
        """
        content = manifest()
        content[ManifestKey.ITEMS.key][1][ManifestKey.DEPENDS_ON.key] = []
        with pytest.raises(PlanValidationError) as error:
            PlanValidator(content).validate()
        assert [type(problem) for problem in error.value.problems] == [
            DependsOnMergedNotDependedOn
        ]

    def test_the_plan_under_test_is_valid(self):
        """
        Listing an entry in both lists passes validation.
        """
        PlanValidator(manifest()).validate()


class TestWhatAMergedDependencyHoldsBack:
    """
    A pull request out of draft is enough to build on unless the merge is required.
    """

    def test_a_ready_pull_request_does_not_release_the_dependent(self):
        """
        Out of draft but unmerged, the base keeps the dependent from starting.
        """
        resolver = resolver_with(merged=False)
        dependent = resolver.plan.items_by_identifier[DEPENDENT]
        assert resolver.resolve(BASE).is_ready_to_unblock_dependents()
        assert not resolver.dependencies_are_ready(dependent)

    def test_the_merge_releases_the_dependent(self):
        """
        Once the base has merged the dependent's dependencies are ready.
        """
        resolver = resolver_with(merged=True)
        dependent = resolver.plan.items_by_identifier[DEPENDENT]
        assert resolver.dependencies_are_ready(dependent)

    @pytest.mark.parametrize("merged", [False, True])
    def test_the_readiness_check_reports_the_merge(self, merged: bool):
        """
        The dependency is reported ready exactly when it has merged.
        """
        plan = Plan.from_mapping(manifest())
        (readiness,) = DependencyReadiness.of_item(
            plan, DEPENDENT, live_pull_requests(merged)
        )
        assert readiness.release is DependencyRelease.MERGED
        assert readiness.is_ready is merged

    def test_a_path_keeps_the_dependent_waiting_for_the_merge(self, tmp_path: Path):
        """
        On a goal's path the dependent awaits the base, named as needing its merge.
        """
        base = DependencyReference(item_identifier=BASE, plan_id=PLAN_UNDER_TEST_ID)
        path = path_with(tmp_path, merged=False)
        step = step_of(
            path, DependencyReference(item_identifier=DEPENDENT, plan_id=base.plan_id)
        )
        assert step.awaited == (base,)
        assert step.awaited_merges == (base,)
        assert step.action is None
        assert step.report(path.position_of(step), ()).awaited_merges == [base.text]

    def test_a_path_starts_the_dependent_after_the_merge(self, tmp_path: Path):
        """
        Once the base has merged the dependent can be started.
        """
        step = step_of(
            path_with(tmp_path, merged=True),
            DependencyReference(item_identifier=DEPENDENT, plan_id=PLAN_UNDER_TEST_ID),
        )
        assert step.awaited == ()
        assert isinstance(step.action, StartNowAction)

