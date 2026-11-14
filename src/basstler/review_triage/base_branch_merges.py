"""
The files of a pull request that only merges of its base branch changed since the commit
its changes are read from.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from basstler.git.commit_range import CommitRange
from basstler.github.pull_request_changes import PullRequestChanges

# %% detection


@dataclass(frozen=True)
class BaseBranchMergeDetection:
    """
    Tells the files whose own change a pull request kept from those it changed again.
    """

    def paths_changed_only_by_merges(
        self, changes: PullRequestChanges
    ) -> frozenset[PurePosixPath]:
        """
        :param changes: A pull request and the files it changes since a commit.
        :return: The files, neither moved nor binary, whose lines the pull request
            itself removes and adds are the same at that commit as at its head; none
            when its changes are read from its merge base.
        """
        git = changes.commits.git
        base_branch = changes.pull_request.base.commit
        start = changes.commits.base_commit
        head = changes.commits.head_commit
        own_change = CommitRange(git, git.merge_base(base_branch, head), head)
        if own_change.base_commit == start:
            return frozenset()
        own_change_at_start = CommitRange(
            git, git.merge_base(base_branch, start), start
        )
        return frozenset(
            file.path
            for file in changes.files
            if file.previous_path is None
            and not file.is_binary
            and own_change.edited_lines(file.path)
            == own_change_at_start.edited_lines(file.path)
        )
