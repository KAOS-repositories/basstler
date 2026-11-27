"""
Splitting a pull request into a commit making only its mechanical changes and one making
every other change.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from basstler.git.commands import GitCommandFailed
from basstler.github.constants import MaintenanceText
from basstler.github.pull_request_changes import PullRequestChanges
from basstler.github.pull_request_description import PullRequestDescription
from basstler.review_triage.exceptions import BaseBranchMergedError, UnprovenSplitError
from basstler.review_triage.mechanical_split import (
    MechanicalSplit,
    MechanicalSplitter,
    MechanicalSummary,
)
from basstler.review_triage.triage import PullRequestTriager

from basstler_testing.scratch_repository import ScratchRepository
from .conftest import committed_pull_request
from .samples import (
    DefinitionMoveEditedSample,
    ModuleMoveSample,
    ImportRespelledMoveSample,
    RenameMixedSample,
    RenamedMoveEditedSample,
    RenameSampledSample,
    SampleTrees,
)

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
) -> MechanicalSplit:
    """
    :return: The edited-move sample pull request, split.
    """
    split = MechanicalSplitter(scratch_repository.git).split(edited_move)
    assert split is not None
    return split


@pytest.fixture
def mixed_rename(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The mixed-rename sample pull request, committed.
    """
    return committed_pull_request(
        scratch_repository, RenameMixedSample.BASE_TREE, RenameMixedSample.HEAD_TREE
    )


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


@pytest.mark.parametrize(
    ("base", "head", "mechanical"),
    [
        (
            DefinitionMoveEditedSample.BASE_TREE,
            DefinitionMoveEditedSample.HEAD_TREE,
            DefinitionMoveEditedSample.MECHANICAL_TREE,
        ),
        (
            RenameMixedSample.BASE_TREE,
            RenameMixedSample.HEAD_TREE,
            RenameMixedSample.MECHANICAL_TREE,
        ),
        (
            RenamedMoveEditedSample.BASE_TREE,
            RenamedMoveEditedSample.HEAD_TREE,
            RenamedMoveEditedSample.MECHANICAL_TREE,
        ),
        (
            ImportRespelledMoveSample.BASE_TREE,
            ImportRespelledMoveSample.HEAD_TREE,
            ImportRespelledMoveSample.MECHANICAL_TREE,
        ),
    ],
    ids=[
        "moved definitions",
        "renames and a rewrapped line",
        "a definition moved under a new name",
        "a moved definition's import respelled",
    ],
)
def test_the_mechanical_commit_makes_every_change_proven_mechanical(
    scratch_repository: ScratchRepository,
    base: SampleTrees,
    head: SampleTrees,
    mechanical: SampleTrees,
):
    """
    Whole files and single statements whose change is mechanical take their head
    version; every other statement keeps its base version, renamed.
    """
    changes = committed_pull_request(scratch_repository, base, head)
    split = MechanicalSplitter(scratch_repository.git).split(changes)
    assert split is not None
    assert tree_files(scratch_repository, split.mechanical_commit) == mechanical.files()


def test_the_remaining_commit_holds_the_head_tree(
    scratch_repository: ScratchRepository,
    edited_move: PullRequestChanges,
    edited_move_split: MechanicalSplit,
):
    git = scratch_repository.git
    assert git.tree_of(edited_move_split.remaining_commit) == git.tree_of(
        edited_move.commits.head_commit
    )


def test_the_mechanical_commit_follows_the_start_commit(
    scratch_repository: ScratchRepository,
    edited_move: PullRequestChanges,
    edited_move_split: MechanicalSplit,
):
    git = scratch_repository.git
    assert git.parents_of(edited_move_split.mechanical_commit) == (
        edited_move.commits.base_commit,
    )
    assert git.parents_of(edited_move_split.remaining_commit) == (
        edited_move_split.mechanical_commit,
    )


def test_splitting_again_gives_the_same_commits(
    scratch_repository: ScratchRepository,
    edited_move: PullRequestChanges,
    edited_move_split: MechanicalSplit,
):
    assert (
        MechanicalSplitter(scratch_repository.git).split(edited_move)
        == edited_move_split
    )


def test_a_wholly_mechanical_pull_request_is_not_split(
    scratch_repository: ScratchRepository,
):
    changes = committed_pull_request(
        scratch_repository,
        RenameSampledSample.BASE_TREE,
        RenameSampledSample.HEAD_TREE,
    )
    assert MechanicalSplitter(scratch_repository.git).split(changes) is None


def test_a_file_needing_review_is_left_out_of_the_mechanical_commit(
    scratch_repository: ScratchRepository,
):
    """
    The package initializer the pull request adds holds code, so it needs review; the
    module still moves into the package and the caller imports it from there.
    """
    changes = committed_pull_request(
        scratch_repository, ModuleMoveSample.BASE_TREE, ModuleMoveSample.HEAD_TREE
    )
    split = MechanicalSplitter(scratch_repository.git).split(changes)
    assert split is not None
    initializer = Path("package/storage/__init__.py")
    expected = {
        path: text
        for path, text in ModuleMoveSample.HEAD_TREE.files().items()
        if path != initializer
    }
    assert tree_files(scratch_repository, split.mechanical_commit) == expected


def test_a_change_started_before_a_base_branch_merge_is_refused(
    scratch_repository: ScratchRepository, mixed_rename: PullRequestChanges
):
    """
    A base branch that moved past the start commit and was merged into the head would be
    lost from the split commits.
    """
    git = scratch_repository.git
    scratch_repository.run_git("checkout", "--quiet", mixed_rename.commits.base_commit)
    scratch_repository.write(Path("unrelated.txt"), "base branch work")
    scratch_repository.commit_everything("base branch")
    base_branch = git.commit_at("HEAD")
    merged_head = git.merge_commit(
        mixed_rename.commits.head_commit, base_branch, "Merge the base branch"
    ).commit
    payload_pull_request = mixed_rename.pull_request
    changes = replace(
        mixed_rename,
        pull_request=replace(
            payload_pull_request,
            base=replace(payload_pull_request.base, commit=base_branch),
        ),
        commits=replace(mixed_rename.commits, head_commit=merged_head),
    )
    with pytest.raises(BaseBranchMergedError):
        MechanicalSplitter(git).split(changes)


# %% the summary


def test_the_description_gains_the_summary_of_the_mechanical_commit(
    edited_move_split: MechanicalSplit,
):
    description = PullRequestDescription(
        edited_move_split.description("https://example.com/pull/1")
    )
    section = description.section(MaintenanceText.MECHANICAL_CHANGES_HEADING)
    assert MechanicalSummary().render(edited_move_split.outcome) in section
    assert edited_move_split.remaining_commit in section


def test_summarising_again_replaces_the_section(edited_move_split: MechanicalSplit):
    once = edited_move_split.description("https://example.com/pull/1")
    pull_request = replace(edited_move_split.pull_request, description=once)
    again = replace(edited_move_split, pull_request=pull_request).description(
        "https://example.com/pull/1"
    )
    assert again == once


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
    edited_move_split: MechanicalSplit,
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
    edited_move_split: MechanicalSplit,
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


def test_a_commit_the_triage_cannot_prove_mechanical_is_refused(
    scratch_repository: ScratchRepository, edited_move: PullRequestChanges
):
    """
    The pull request's head rewords a docstring, which is not mechanical.
    """
    triager = PullRequestTriager().file_triager(edited_move)
    with pytest.raises(UnprovenSplitError):
        MechanicalSplitter.prove(edited_move, edited_move.commits.head_commit, triager)
