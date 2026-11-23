"""
Tests for :mod:`basstler.review_triage.recorded_plans` and
:mod:`basstler.review_triage.plan_replay`: a file proven mechanical by replaying, on the
base, the code modification plan a commit records.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.comparison import MechanicalChange, MechanicalFile
from basstler.review_triage.exceptions import UnknownRecordedPlanError
from basstler.review_triage.plan_replay import ReplayedPlanChange
from basstler.review_triage.recorded_plans import (
    PLAN_TRAILER,
    PlanRecord,
    RecordedPlan,
)
from basstler.review_triage.triage import PullRequestTriager

from basstler_testing.scratch_repository import ScratchRepository
from .conftest import commit_trees, committed_pull_request, pull_request_between
from .samples import WorkspacePackagesSample

RECORDING_MESSAGE = (
    f"Split the package\n\n{PLAN_TRAILER}: {RecordedPlan.WORKSPACE_PACKAGES}\n"
)
"""
A commit message recording that the commit applied the workspace packages plan.
"""

EDITED_MODULE = Path("packages/core/src/basstler/bash.py")
"""
A file of the sample's head that :func:`edited_beyond_the_plan` changes further.
"""

IMPORT_REWRITTEN = PurePosixPath("packages/core/tests/test_bash.py")
"""
A test of the sample whose relative import of a shared helper the plan rewrites as an
absolute one, following the helper's module to where the sample moves it.
"""

# %% recording a plan


def test_a_commit_records_the_plan_its_trailer_names(
    scratch_repository: ScratchRepository,
):
    commits = commit_trees(
        scratch_repository,
        {Path("a.txt"): "a\n"},
        {Path("a.txt"): "b\n"},
        RECORDING_MESSAGE,
    )

    assert PlanRecord.recorded_in(commits) == (
        PlanRecord(commits.head_commit, RecordedPlan.WORKSPACE_PACKAGES),
    )


def test_a_trailer_names_the_release_that_applied_the_plan(
    scratch_repository: ScratchRepository,
):
    release = "3.25.2"
    commits = commit_trees(
        scratch_repository,
        {Path("a.txt"): "a\n"},
        {Path("a.txt"): "b\n"},
        f"Split the package\n\n{PLAN_TRAILER}: {RecordedPlan.WORKSPACE_PACKAGES} "
        f"{PlanRecord.release_prefix}{release}\n",
    )

    assert PlanRecord.recorded_in(commits) == (
        PlanRecord(commits.head_commit, RecordedPlan.WORKSPACE_PACKAGES, release),
    )


def test_a_commit_without_the_trailer_records_no_plan(
    scratch_repository: ScratchRepository,
):
    commits = commit_trees(
        scratch_repository, {Path("a.txt"): "a\n"}, {Path("a.txt"): "b\n"}
    )

    assert PlanRecord.recorded_in(commits) == ()


def test_an_argument_names_a_commit_and_the_plan_it_applied():
    assert PlanRecord.from_argument(
        f"d9dd4b5b{PlanRecord.separator}{RecordedPlan.WORKSPACE_PACKAGES}"
    ) == PlanRecord("d9dd4b5b", RecordedPlan.WORKSPACE_PACKAGES)


def test_an_argument_naming_no_known_plan_is_refused():
    with pytest.raises(UnknownRecordedPlanError):
        PlanRecord.from_argument(f"d9dd4b5b{PlanRecord.separator}no-such-plan")


# %% replaying the plan in a triage


@pytest.fixture
def recorded_split(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The sample split committed with a message recording the plan.
    """
    return committed_pull_request(
        scratch_repository,
        WorkspacePackagesSample.BASE_TREE,
        WorkspacePackagesSample.HEAD_TREE,
        RECORDING_MESSAGE,
    )


@pytest.fixture
def unrecorded_split(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The sample split committed with a message recording nothing.
    """
    return committed_pull_request(
        scratch_repository,
        WorkspacePackagesSample.BASE_TREE,
        WorkspacePackagesSample.HEAD_TREE,
    )


def replayed_paths(
    changes: PullRequestChanges, triager: PullRequestTriager
) -> set[PurePosixPath]:
    """
    :param changes: A pull request and the files it changes.
    :param triager: How it is triaged.
    :return: The files the triage proves mechanical by replaying the workspace
        packages plan.
    """
    return {
        verdict.change.path
        for verdict in triager.triage(changes).mechanical_files
        if ReplayedPlanChange[RecordedPlan.WORKSPACE_PACKAGES.name] in verdict.kinds
    }


def test_every_file_a_recorded_plan_changed_is_mechanical(
    recorded_split: PullRequestChanges,
):
    assert replayed_paths(recorded_split, PullRequestTriager()) == {
        change.path for change in recorded_split.files
    }


def test_a_plan_named_on_the_command_line_is_replayed_too(
    unrecorded_split: PullRequestChanges,
):
    triager = PullRequestTriager(
        plan_records=(
            PlanRecord(
                unrecorded_split.commits.head_commit, RecordedPlan.WORKSPACE_PACKAGES
            ),
        )
    )

    assert replayed_paths(unrecorded_split, triager) == {
        change.path for change in unrecorded_split.files
    }


def test_without_a_record_a_rewritten_import_following_a_module_move_is_mechanical(
    unrecorded_split: PullRequestChanges,
):
    """
    The relative import the plan rewrites resolves to the helper's old module, whose
    detected move the absolute import follows, so no file needs review.
    """
    triage = PullRequestTriager().triage(unrecorded_split)

    assert triage.files_needing_review == ()


def test_a_plan_recorded_before_the_triaged_commits_is_not_replayed(
    unrecorded_split: PullRequestChanges,
):
    triager = PullRequestTriager(
        plan_records=(
            PlanRecord(
                unrecorded_split.commits.base_commit, RecordedPlan.WORKSPACE_PACKAGES
            ),
        )
    )

    assert replayed_paths(unrecorded_split, triager) == set()


@pytest.fixture
def edited_beyond_the_plan(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The sample split recording the plan, one of its modules edited further.
    """
    head = WorkspacePackagesSample.HEAD_TREE.files()
    head[EDITED_MODULE] += "\nSHELL_NAME = 'bash'\n"
    return pull_request_between(
        commit_trees(
            scratch_repository,
            WorkspacePackagesSample.BASE_TREE.files(),
            head,
            RECORDING_MESSAGE,
        )
    )


def test_a_file_changed_beyond_the_plan_needs_review(
    edited_beyond_the_plan: PullRequestChanges,
):
    triage = PullRequestTriager().triage(edited_beyond_the_plan)

    assert {verdict.change.path for verdict in triage.files_needing_review} == {
        PurePosixPath(EDITED_MODULE)
    }


def test_a_moved_file_whose_imports_the_plan_rewrote_is_a_replayed_move(
    recorded_split: PullRequestChanges,
):
    verdict = next(
        verdict
        for verdict in PullRequestTriager().triage(recorded_split).files
        if verdict.change.path == IMPORT_REWRITTEN
    )

    assert verdict == MechanicalFile(
        verdict.change,
        frozenset(
            {
                ReplayedPlanChange[RecordedPlan.WORKSPACE_PACKAGES.name],
                MechanicalChange.MOVE,
            }
        ),
    )
