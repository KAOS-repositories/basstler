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
from basstler.review_triage.comparison import MechanicalChange
from basstler.review_triage.triage import PullRequestTriager

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
    :param tree: The files to write over the checkout.
    :return: The commit holding them.
    """
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
    scratch_repository.run_git("merge", "--quiet", "--no-edit", update)
    head = commit_tree(scratch_repository, BaseBranchMergeSample.HEAD_TREE)
    return ReviewedHistory(scratch_repository, update, reviewed, head)


# %% the range


def test_the_changes_start_at_the_commit_given(reviewed_history: ReviewedHistory):
    changes = reviewed_history.read(reviewed_history.reviewed_commit)
    assert changes.commits.base_commit == reviewed_history.reviewed_commit


# %% the verdicts


def test_files_only_the_base_branch_changed_since_the_review_are_mechanical(
    reviewed_history: ReviewedHistory,
):
    """
    A file the pull request left alone and one whose own change the merge left as it was
    are both attributed to the merge.
    """
    triage = PullRequestTriager().triage(
        reviewed_history.read(reviewed_history.reviewed_commit)
    )
    assert {file.change.path: file.kinds for file in triage.mechanical_files} == {
        PurePosixPath("limits.py"): frozenset({MechanicalChange.BASE_BRANCH_MERGE}),
        PurePosixPath("numbers.py"): frozenset({MechanicalChange.BASE_BRANCH_MERGE}),
    }


def test_a_file_the_pull_request_changed_since_the_review_needs_review(
    reviewed_history: ReviewedHistory,
):
    triage = PullRequestTriager().triage(
        reviewed_history.read(reviewed_history.reviewed_commit)
    )
    assert [file.change.path for file in triage.files_needing_review] == [
        PurePosixPath("greeting.py")
    ]


def test_the_whole_pull_request_is_triaged_from_its_merge_base(
    reviewed_history: ReviewedHistory,
):
    """
    Without a reviewed commit, only the files the pull request itself changes are
    triaged, and none of them is attributed to a merge.
    """
    triage = PullRequestTriager().triage(reviewed_history.read(None))
    assert [file.change.path for file in triage.files_needing_review] == [
        PurePosixPath("greeting.py"),
        PurePosixPath("numbers.py"),
    ]
    assert triage.mechanical_files == ()
