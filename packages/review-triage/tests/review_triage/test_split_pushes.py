"""
Splitting a pull request again after each push: every split adds commits on top of the
branch, so a newcomer reads every change beyond the mechanical ones in one commit and a
returning reviewer reads only the last push's.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from basstler.git.commands import CommitTrailer
from basstler.git.commit_range import CommitRange
from basstler.github.constants import MaintenanceText
from basstler.github.pull_request_description import PullRequestDescription
from basstler.review_triage.mechanical_split import (
    MechanicalSplit,
    MechanicalSplitter,
    SplitCommitRole,
)

from basstler_testing.scratch_repository import ScratchRepository
from .conftest import pull_request_between
from .samples import SampleTrees, SplitPushesSample

PULL_REQUEST_URL = "https://example.com/pull/1"
"""
The page the sample pull request's description links its commits under.
"""

# %% the pull request's branch


@dataclass
class PushedBranch:
    """
    A pull request's branch the author pushes to and the split adds to, as a remote
    holds it.
    """

    repository: ScratchRepository
    """
    The repository holding every commit.
    """

    base: str
    """
    The base branch's tip.
    """

    head: str
    """
    The branch's head.
    """

    @classmethod
    def started_at(
        cls, repository: ScratchRepository, base: SampleTrees
    ) -> PushedBranch:
        """
        :param repository: A repository with nothing committed.
        :param base: The base branch's tree.
        :return: A branch with nothing pushed yet, on a base branch recording *base*.
        """
        for path, text in base.files().items():
            repository.write(path, text)
        repository.commit_everything(base)
        commit = repository.git.commit_at("HEAD")
        return cls(repository, commit, commit)

    def commit(self, parent: str, tree: SampleTrees) -> str:
        """
        :param parent: The commit to commit on.
        :param tree: The tree the commit records.
        :return: The commit.
        """
        self.repository.run_git("checkout", "--quiet", "--detach", parent)
        self.repository.run_git("rm", "-r", "--quiet", ".")
        for path, text in tree.files().items():
            self.repository.write(path, text)
        self.repository.commit_everything(tree)
        return self.repository.git.commit_at("HEAD")

    def push(self, tree: SampleTrees) -> str:
        """
        Push one commit recording *tree* on top of the head.

        :param tree: The tree the pushed commit records.
        :return: The pushed commit.
        """
        self.head = self.commit(self.head, tree)
        return self.head

    def split(self) -> MechanicalSplit | None:
        """
        Split the branch and take the split's last commit as its head.

        :return: The split, ``None`` when there was nothing to split.
        """
        git = self.repository.git
        changes = pull_request_between(
            CommitRange(git, git.merge_base(self.base, self.head), self.head)
        )
        split = MechanicalSplitter(git).split(changes)
        if split is not None:
            self.head = split.remaining_commit
        return split

    def proven_split(self) -> MechanicalSplit:
        """
        :return: The split of the branch, which the test expects there to be.
        """
        split = self.split()
        assert split is not None
        return split

    def tree_files(self, commit: str) -> dict[Path, str]:
        """
        :param commit: A commit.
        :return: The content of each file of its tree, by its path in the tree.
        """
        paths = self.repository.git.run("ls-tree", "-r", "--name-only", commit)
        return {
            Path(path): self.repository.run_git("show", f"{commit}:{path}").stdout
            for path in paths.splitlines()
        }

    def changed_paths(self, start: str, end: str) -> set[Path]:
        """
        :param start: A commit.
        :param end: Another commit.
        :return: The files whose content differs between the two.
        """
        names = self.repository.git.run("diff", "--name-only", start, end)
        return {Path(name) for name in names.splitlines()}


@pytest.fixture
def branch(scratch_repository: ScratchRepository) -> PushedBranch:
    """
    :return: The sample pull request's branch after its first push, not yet split.
    """
    branch = PushedBranch.started_at(scratch_repository, SplitPushesSample.BASE_TREE)
    branch.push(SplitPushesSample.FIRST_PUSH)
    return branch


@pytest.fixture
def first_split(branch: PushedBranch) -> MechanicalSplit:
    """
    :return: The split of the branch's first push.
    """
    return branch.proven_split()


@pytest.fixture
def second_head(branch: PushedBranch, first_split: MechanicalSplit) -> str:
    """
    :return: The head of the push the author makes after the first split, renaming a
        method and rewording a text.
    """
    return branch.push(SplitPushesSample.SECOND_PUSH)


@pytest.fixture
def second_split(branch: PushedBranch, second_head: str) -> MechanicalSplit:
    """
    :return: The split of the second push.
    """
    return branch.proven_split()


# %% the first split


def test_the_first_mechanical_commit_follows_the_merge_base(
    branch: PushedBranch, first_split: MechanicalSplit
):
    git = branch.repository.git
    assert git.parents_of(first_split.mechanical_commit) == (branch.base,)
    assert (
        branch.tree_files(first_split.mechanical_commit)
        == SplitPushesSample.FIRST_MECHANICAL.files()
    )


def test_the_first_split_merges_the_head_into_the_mechanical_commit(
    branch: PushedBranch, scratch_repository: ScratchRepository
):
    """
    The head stays in the history, so the author's commits are all kept.
    """
    head = branch.head
    split = branch.proven_split()
    git = scratch_repository.git
    assert git.parents_of(split.remaining_commit) == (split.mechanical_commit, head)
    assert git.tree_of(split.remaining_commit) == git.tree_of(head)


def test_the_first_split_makes_no_commits_for_a_push(first_split: MechanicalSplit):
    """
    Every change of the pull request is new to every reviewer.
    """
    assert first_split.push_mechanical_commit is None
    assert first_split.push_remaining_commit is None


def test_a_split_is_a_fast_forward_of_the_head(branch: PushedBranch):
    head = branch.head
    split = branch.proven_split()
    assert branch.repository.git.contains(head, split.remaining_commit)


def test_a_head_already_split_is_not_split_again(
    branch: PushedBranch, first_split: MechanicalSplit
):
    assert branch.split() is None


def test_a_branch_with_nothing_mechanical_is_not_split(
    scratch_repository: ScratchRepository,
):
    branch = PushedBranch.started_at(scratch_repository, SplitPushesSample.SECOND_PUSH)
    branch.push(SplitPushesSample.LOGIC_ONLY_PUSH)
    assert branch.split() is None


def test_a_wholly_mechanical_branch_is_not_split(
    scratch_repository: ScratchRepository,
):
    """
    Marking its files viewed leaves nothing to read, so a split would add nothing.
    """
    branch = PushedBranch.started_at(scratch_repository, SplitPushesSample.SECOND_PUSH)
    branch.push(SplitPushesSample.RENAME_ONLY_PUSH)
    assert branch.split() is None


# %% a push after a split


def test_the_whole_mechanical_commit_follows_the_previous_one(
    branch: PushedBranch, first_split: MechanicalSplit, second_split: MechanicalSplit
):
    """
    It makes every mechanical change of the pull request, the first push's too.
    """
    git = branch.repository.git
    assert git.parents_of(second_split.mechanical_commit) == (
        first_split.mechanical_commit,
    )
    assert (
        branch.tree_files(second_split.mechanical_commit)
        == SplitPushesSample.SECOND_WHOLE_MECHANICAL.files()
    )


def test_the_push_s_mechanical_commit_follows_the_previous_split(
    branch: PushedBranch, first_split: MechanicalSplit, second_split: MechanicalSplit
):
    """
    It makes only the push's mechanical changes.
    """
    assert second_split.push_mechanical_commit is not None
    git = branch.repository.git
    assert git.parents_of(second_split.push_mechanical_commit) == (
        first_split.remaining_commit,
    )
    assert (
        branch.tree_files(second_split.push_mechanical_commit)
        == SplitPushesSample.SECOND_PUSH_MECHANICAL.files()
    )


def test_the_push_s_remaining_commit_merges_the_head_into_its_mechanical_commit(
    branch: PushedBranch, second_head: str, second_split: MechanicalSplit
):
    assert second_split.push_remaining_commit is not None
    git = branch.repository.git
    assert git.parents_of(second_split.push_remaining_commit) == (
        second_split.push_mechanical_commit,
        second_head,
    )
    assert git.tree_of(second_split.push_remaining_commit) == git.tree_of(second_head)


def test_the_remaining_commit_merges_the_push_s_into_the_whole_mechanical_commit(
    branch: PushedBranch, second_head: str, second_split: MechanicalSplit
):
    git = branch.repository.git
    assert git.parents_of(second_split.remaining_commit) == (
        second_split.mechanical_commit,
        second_split.push_remaining_commit,
    )
    assert git.tree_of(second_split.remaining_commit) == git.tree_of(second_head)


def test_a_newcomer_reads_every_push_s_changes_beyond_the_mechanical_ones(
    branch: PushedBranch, second_split: MechanicalSplit
):
    """
    The first push's changed default value and the second push's reworded text, without
    either push's renames.
    """
    assert branch.changed_paths(
        second_split.mechanical_commit, second_split.remaining_commit
    ) == {Path("pkg/scores.py"), Path("pkg/report.py")}
    assert (
        branch.tree_files(second_split.mechanical_commit)[Path("pkg/scores.py")]
        == SplitPushesSample.SECOND_WHOLE_MECHANICAL.files()[Path("pkg/scores.py")]
    )


def test_a_returning_reviewer_reads_only_the_push_s_changes_beyond_the_mechanical_ones(
    branch: PushedBranch, second_split: MechanicalSplit
):
    """
    Only the reworded text of the report, not the rename the push also makes.
    """
    assert second_split.push_mechanical_commit is not None
    assert second_split.push_remaining_commit is not None
    assert branch.changed_paths(
        second_split.push_mechanical_commit, second_split.push_remaining_commit
    ) == {Path("pkg/report.py")}


def test_splitting_a_push_again_gives_the_same_commits(
    branch: PushedBranch, second_head: str, second_split: MechanicalSplit
):
    git = branch.repository.git
    changes = pull_request_between(
        CommitRange(git, git.merge_base(branch.base, second_head), second_head)
    )
    assert MechanicalSplitter(git).split(changes) == second_split


def test_the_split_after_a_later_push_starts_from_the_newest_split(
    branch: PushedBranch, second_split: MechanicalSplit
):
    branch.push(SplitPushesSample.RENAME_ONLY_PUSH)
    third_split = branch.proven_split()
    git = branch.repository.git
    assert third_split.push_mechanical_commit is not None
    assert git.parents_of(third_split.push_mechanical_commit) == (
        second_split.remaining_commit,
    )
    assert git.parents_of(third_split.mechanical_commit) == (
        second_split.mechanical_commit,
    )


# %% pushes of one kind


def test_a_push_with_nothing_mechanical_adds_no_mechanical_commits(
    branch: PushedBranch, second_split: MechanicalSplit
):
    """
    The push's remaining commit follows the previous split, and the whole mechanical
    commit stays the previous one, the mechanical changes being the same.
    """
    logic_head = branch.push(SplitPushesSample.LOGIC_ONLY_PUSH)
    split = branch.proven_split()
    git = branch.repository.git
    assert split.push_mechanical_commit is None
    assert git.parents_of(split.push_remaining_commit or "") == (
        second_split.remaining_commit,
        logic_head,
    )
    assert split.mechanical_commit == second_split.mechanical_commit
    assert git.parents_of(split.remaining_commit) == (
        second_split.mechanical_commit,
        split.push_remaining_commit,
    )


def test_a_wholly_mechanical_push_leaves_its_remaining_commit_empty(
    branch: PushedBranch, second_split: MechanicalSplit
):
    """
    A returning reviewer opening it sees there is nothing to read.
    """
    branch.push(SplitPushesSample.RENAME_ONLY_PUSH)
    split = branch.proven_split()
    git = branch.repository.git
    assert split.push_mechanical_commit is not None
    assert git.tree_of(split.push_mechanical_commit) == git.tree_of(
        split.push_remaining_commit or ""
    )
    assert (
        branch.tree_files(split.mechanical_commit)
        == SplitPushesSample.RENAME_ONLY_WHOLE_MECHANICAL.files()
    )


def test_a_push_merging_the_base_branch_makes_only_the_whole_commits(
    branch: PushedBranch, second_split: MechanicalSplit
):
    """
    The base branch's changes would read as the push's own, so the push gets no commits
    of its own; the whole mechanical commit starts from the new merge base.
    """
    git = branch.repository.git
    branch.base = branch.commit(branch.base, SplitPushesSample.BASE_ADVANCED)
    merged_head = git.merge_commit(branch.head, branch.base, "Merge the base").commit
    assert branch.tree_files(merged_head) == SplitPushesSample.MERGED_BASE_PUSH.files()
    branch.head = merged_head
    split = branch.proven_split()
    assert split.push_mechanical_commit is None
    assert split.push_remaining_commit is None
    assert git.parents_of(split.remaining_commit) == (
        split.mechanical_commit,
        merged_head,
    )
    assert git.parents_of(split.mechanical_commit) == (second_split.mechanical_commit,)
    assert (
        branch.tree_files(split.mechanical_commit)
        == SplitPushesSample.MERGED_BASE_WHOLE_MECHANICAL.files()
    )


# %% the history the split is found in


def test_a_branch_rewritten_without_the_split_is_split_from_the_merge_base(
    branch: PushedBranch, second_split: MechanicalSplit
):
    branch.head = branch.base
    branch.push(SplitPushesSample.SECOND_PUSH)
    split = branch.proven_split()
    git = branch.repository.git
    assert git.parents_of(split.mechanical_commit) == (branch.base,)
    assert split.push_remaining_commit is None


def test_the_newest_split_is_found_beyond_a_merge_s_first_parent(
    branch: PushedBranch, first_split: MechanicalSplit
):
    """
    An author who committed before pulling the split merges it in as the second parent.
    """
    git = branch.repository.git
    first_head = git.parents_of(first_split.remaining_commit)[1]
    local = branch.commit(first_head, SplitPushesSample.SECOND_PUSH)
    branch.head = git.merge_commit(
        local, first_split.remaining_commit, "Merge the split"
    ).commit
    split = branch.proven_split()
    assert split.push_mechanical_commit is not None
    assert git.parents_of(split.push_mechanical_commit) == (
        first_split.remaining_commit,
    )


@pytest.mark.parametrize(
    ("commit", "role"),
    [
        ("mechanical_commit", SplitCommitRole.WHOLE_MECHANICAL),
        ("remaining_commit", SplitCommitRole.WHOLE_REMAINING),
        ("push_mechanical_commit", SplitCommitRole.PUSH_MECHANICAL),
        ("push_remaining_commit", SplitCommitRole.PUSH_REMAINING),
    ],
)
def test_each_split_commit_names_its_role(
    branch: PushedBranch, second_split: MechanicalSplit, commit, role
):
    git = branch.repository.git
    split_commits = {
        "mechanical_commit": second_split.mechanical_commit,
        "remaining_commit": second_split.remaining_commit,
        "push_mechanical_commit": second_split.push_mechanical_commit,
        "push_remaining_commit": second_split.push_remaining_commit,
    }
    assert git.trailer_value(split_commits[commit] or "", CommitTrailer.SPLIT) == role


# %% the description


def test_the_description_links_the_whole_and_the_push_s_remaining_commits(
    second_split: MechanicalSplit,
):
    description = PullRequestDescription(second_split.description(PULL_REQUEST_URL))
    section = description.section(MaintenanceText.MECHANICAL_CHANGES_HEADING)
    assert f"{PULL_REQUEST_URL}/commits/{second_split.remaining_commit}" in section
    assert f"{PULL_REQUEST_URL}/commits/{second_split.push_remaining_commit}" in section


def test_the_first_description_links_only_the_whole_remaining_commit(
    first_split: MechanicalSplit,
):
    description = PullRequestDescription(first_split.description(PULL_REQUEST_URL))
    section = description.section(MaintenanceText.MECHANICAL_CHANGES_HEADING)
    assert section.count(f"{PULL_REQUEST_URL}/commits/") == 1
