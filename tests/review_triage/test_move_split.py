"""
Splitting a pull request into a commit that only moves definitions and one making every
other change.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.git.commands import GitCommandFailed
from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.exceptions import UnprovenMoveError
from basstler.review_triage.move_split import MoveSplit, MoveSplitter
from basstler.review_triage.triage import PullRequestTriager

from ..scratch_repository import ScratchRepository
from .conftest import committed_pull_request
from .samples import DefinitionMoveEditedSample, ModuleMoveSample

# %% fixtures


@pytest.fixture
def edited_move(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The edited-move sample pull request, committed.
    """
    return committed_pull_request(
        scratch_repository,
        DefinitionMoveEditedSample.BASE_TREE,
        DefinitionMoveEditedSample.HEAD_TREE,
    )


@pytest.fixture
def edited_move_split(
    scratch_repository: ScratchRepository, edited_move: PullRequestChanges
) -> MoveSplit:
    """
    :return: The edited-move sample pull request, split.
    """
    split = MoveSplitter(scratch_repository.git).split(edited_move)
    assert split is not None
    return split


def tree_files(scratch_repository: ScratchRepository, commit: str) -> dict[Path, str]:
    """
    :param scratch_repository: The repository holding the commit.
    :param commit: A commit.
    :return: The content of each file of its tree, by its path in the tree.
    """
    paths = scratch_repository.git.run("ls-tree", "-r", "--name-only", commit)
    return {
        Path(path): scratch_repository.run_git("show", f"{commit}:{path}").stdout
        for path in paths.splitlines()
    }


# %% the two commits


def test_the_move_commit_only_moves_the_definitions(
    scratch_repository: ScratchRepository, edited_move_split: MoveSplit
):
    assert (
        tree_files(scratch_repository, edited_move_split.move_commit)
        == DefinitionMoveEditedSample.MOVE_ONLY_TREE.files()
    )


def test_the_remaining_commit_holds_the_head_tree(
    scratch_repository: ScratchRepository,
    edited_move: PullRequestChanges,
    edited_move_split: MoveSplit,
):
    git = scratch_repository.git
    assert git.tree_of(edited_move_split.remaining_commit) == git.tree_of(
        edited_move.commits.head_commit
    )


def test_the_move_commit_follows_the_merge_base(
    scratch_repository: ScratchRepository,
    edited_move: PullRequestChanges,
    edited_move_split: MoveSplit,
):
    git = scratch_repository.git
    assert git.parents_of(edited_move_split.move_commit) == (
        edited_move.commits.base_commit,
    )
    assert git.parents_of(edited_move_split.remaining_commit) == (
        edited_move_split.move_commit,
    )


def test_splitting_again_gives_the_same_commits(
    scratch_repository: ScratchRepository,
    edited_move: PullRequestChanges,
    edited_move_split: MoveSplit,
):
    assert MoveSplitter(scratch_repository.git).split(edited_move) == edited_move_split


def test_a_pull_request_moving_no_definition_is_not_split(
    scratch_repository: ScratchRepository,
):
    changes = committed_pull_request(
        scratch_repository, ModuleMoveSample.BASE_TREE, ModuleMoveSample.HEAD_TREE
    )
    assert MoveSplitter(scratch_repository.git).split(changes) is None


# %% replacing the branch


@pytest.fixture
def published_branch(
    scratch_repository: ScratchRepository,
    edited_move: PullRequestChanges,
    tmp_path: Path,
) -> Path:
    """
    :return: A bare repository whose branch of the pull request points at its head.
    """
    remote = tmp_path / "published.git"
    scratch_repository.run_git("init", "--quiet", "--bare", str(remote))
    scratch_repository.run_git(
        "push",
        "--quiet",
        str(remote),
        f"{edited_move.commits.head_commit}:refs/heads/"
        f"{edited_move.pull_request.head.branch}",
    )
    return remote


def test_publishing_replaces_the_pull_request_branch(
    scratch_repository: ScratchRepository,
    edited_move: PullRequestChanges,
    edited_move_split: MoveSplit,
    published_branch: Path,
):
    edited_move_split.publish(scratch_repository.git, str(published_branch))
    branch = f"refs/heads/{edited_move.pull_request.head.branch}"
    published = scratch_repository.git.run(
        "ls-remote", str(published_branch), branch
    ).split()[0]
    assert published == edited_move_split.remaining_commit


def test_a_branch_moved_since_it_was_read_is_not_replaced(
    scratch_repository: ScratchRepository,
    edited_move: PullRequestChanges,
    edited_move_split: MoveSplit,
    published_branch: Path,
):
    scratch_repository.run_git(
        "push",
        "--quiet",
        "--force",
        str(published_branch),
        f"{edited_move.commits.base_commit}:refs/heads/"
        f"{edited_move.pull_request.head.branch}",
    )
    with pytest.raises(GitCommandFailed):
        edited_move_split.publish(scratch_repository.git, str(published_branch))


# %% the proof


def test_a_move_commit_the_triage_cannot_prove_is_refused(
    scratch_repository: ScratchRepository, edited_move: PullRequestChanges
):
    """
    A triager without judgments proves no file mechanical, so the split is refused.
    """
    splitter = MoveSplitter(scratch_repository.git, PullRequestTriager(judgments=()))
    with pytest.raises(UnprovenMoveError):
        splitter.split(edited_move)
