"""
Triaging a pull request from the commit it was last reviewed at, after it merged an
update of its base branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

import pytest

from basstler.github.pull_request_changes import (
    PullRequestChanges,
    PullRequestChangesReader,
)
from basstler.review_triage.comparison import ChangeKinds, MechanicalChange
from basstler.review_triage.triage import PullRequestTriager, TriageOutcome

from ..scratch_repository import ScratchRepository
from .conftest import SAMPLE_REPOSITORY, OnePullRequestReader
from .samples import BaseBranchMergeSample, DescriptionSample, PullRequestSample

# %% the history


@dataclass(frozen=True)
class ReviewedHistory:
    """
    A pull request's history in a scratch repository: reviewed, then merging its base
    branch, then changed again.
    """

    repository: ScratchRepository
    """
    The repository holding the history.
    """

    base_branch_commit: str
    """
    The base branch's commit after its update.
    """

    reviewed_commit: str
    """
    The pull request's head commit when it was reviewed.
    """

    head_commit: str
    """
    The pull request's head commit now.
    """

    def read(self, since: str | None) -> PullRequestChanges:
        """
        :param since: The commit the changes are read from, the merge base when
            ``None``.
        :return: The pull request's changes.
        """
        payload = PullRequestSample.PAYLOAD.payload()
        payload["base"]["sha"] = self.base_branch_commit
        payload["head"]["sha"] = self.head_commit
        payload["body"] = DescriptionSample.WITHOUT_DECLARATION.read()
        return PullRequestChangesReader(
            self.repository.git, OnePullRequestReader(payload)
        ).read(SAMPLE_REPOSITORY, payload["number"], since)


def commit_tree(
    scratch_repository: ScratchRepository, tree: BaseBranchMergeSample
) -> str:
    """
    :param scratch_repository: The repository to commit in.
    :param tree: The files the commit holds, in place of the checkout's.
    :return: The commit holding them.
    """
    scratch_repository.run_git("rm", "-r", "--quiet", "--ignore-unmatch", ".")
    for path, text in tree.files().items():
        scratch_repository.write(path, text)
    scratch_repository.commit_everything(tree)
    return scratch_repository.git.commit_at("HEAD")


@pytest.fixture
def reviewed_history(scratch_repository: ScratchRepository) -> ReviewedHistory:
    """
    :return: The sample history, committed.
    """
    start = commit_tree(scratch_repository, BaseBranchMergeSample.BASE_TREE)
    scratch_repository.run_git("checkout", "--quiet", "-b", "feature")
    reviewed = commit_tree(scratch_repository, BaseBranchMergeSample.REVIEWED_TREE)
    scratch_repository.run_git("checkout", "--quiet", start)
    update = commit_tree(scratch_repository, BaseBranchMergeSample.BASE_BRANCH_UPDATE)
    scratch_repository.run_git("checkout", "--quiet", "feature")
    scratch_repository.run_git(
        "merge", "--quiet", "--no-edit", "--strategy-option=theirs", update
    )
    head = commit_tree(scratch_repository, BaseBranchMergeSample.HEAD_TREE)
    return ReviewedHistory(scratch_repository, update, reviewed, head)


# %% the range


def test_the_changes_start_at_the_commit_given(reviewed_history: ReviewedHistory):
    changes = reviewed_history.read(reviewed_history.reviewed_commit)
    assert changes.commits.base_commit == reviewed_history.reviewed_commit


def test_only_files_the_pull_request_changes_are_read_since_a_commit(
    reviewed_history: ReviewedHistory,
):
    """
    A file only the base branch changed is not part of the pull request, so GitHub could
    not mark it viewed.
    """
    changes = reviewed_history.read(reviewed_history.reviewed_commit)
    assert [file.path for file in changes.files] == [
        PurePosixPath("greeting.py"),
        PurePosixPath("numbers.py"),
        PurePosixPath("service/errors.py"),
        PurePosixPath("service/requests.py"),
        PurePosixPath("settings.py"),
        PurePosixPath("text/words.py"),
    ]


# %% the verdicts


@pytest.fixture
def triage_since_review(reviewed_history: ReviewedHistory) -> TriageOutcome:
    """
    :return: The sample pull request triaged since its reviewed commit.
    """
    return PullRequestTriager().triage(
        reviewed_history.read(reviewed_history.reviewed_commit)
    )


def mechanical_kinds(triage: TriageOutcome) -> dict[PurePosixPath, ChangeKinds]:
    """
    :param triage: A triaged pull request.
    :return: What the change of each of its mechanical files consists of, by path.
    """
    return {file.change.path: file.kinds for file in triage.mechanical_files}


def test_a_file_whose_own_change_a_merge_kept_is_mechanical(
    triage_since_review: TriageOutcome,
):
    """
    A file whose own change the merge left as it was is attributed to the merge.
    """
    assert mechanical_kinds(triage_since_review)[
        PurePosixPath("numbers.py")
    ] == frozenset({MechanicalChange.BASE_BRANCH_MERGE})


def test_a_file_the_base_branch_moved_is_attributed_to_the_merge(
    triage_since_review: TriageOutcome,
):
    """
    The base branch moved a file whose own change the pull request kept.
    """
    assert mechanical_kinds(triage_since_review)[
        PurePosixPath("text/words.py")
    ] == frozenset({MechanicalChange.BASE_BRANCH_MERGE})


def test_a_conflicted_file_whose_own_change_the_merge_kept_is_mechanical(
    triage_since_review: TriageOutcome,
):
    """
    Merging the reviewed commit with the base branch conflicts on the file, but the
    lines the pull request itself edits are the same as at the review.
    """
    assert mechanical_kinds(triage_since_review)[
        PurePosixPath("settings.py")
    ] == frozenset({MechanicalChange.BASE_BRANCH_MERGE})


def test_a_definition_moved_into_a_module_the_base_branch_added_is_mechanical(
    triage_since_review: TriageOutcome,
):
    """
    Since the review, the base branch added a module and the pull request moved a class
    into it, so only the move is the pull request's.
    """
    kinds = mechanical_kinds(triage_since_review)
    assert kinds[PurePosixPath("service/requests.py")] == frozenset(
        {MechanicalChange.DEFINITIONS_MOVED_IN}
    )
    assert kinds[PurePosixPath("service/errors.py")] == frozenset(
        {MechanicalChange.DEFINITIONS_MOVED_OUT}
    )


def test_a_file_the_pull_request_changed_since_the_review_needs_review(
    triage_since_review: TriageOutcome,
):
    assert [file.change.path for file in triage_since_review.files_needing_review] == [
        PurePosixPath("greeting.py")
    ]


def test_the_whole_pull_request_is_triaged_from_its_merge_base(
    reviewed_history: ReviewedHistory,
):
    """
    Without a reviewed commit, no file is attributed to a merge.
    """
    triage = PullRequestTriager().triage(reviewed_history.read(None))
    assert not any(
        MechanicalChange.BASE_BRANCH_MERGE in kinds
        for kinds in mechanical_kinds(triage).values()
    )
