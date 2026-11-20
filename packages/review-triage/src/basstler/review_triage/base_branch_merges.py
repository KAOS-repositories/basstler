"""
A pull request's changes since a commit, told apart into those merges of its base branch
made and those it made itself.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from basstler.git.commit_range import CommitRange, FileVersions
from basstler.github.pull_request_changes import PullRequestChanges

REVIEWED_ON_BASE_MESSAGE = "Merge the base branch into the reviewed commit"
"""
The message of the commit merging the commit the changes are read from with the base
branch.
"""

# %% the separated changes


@dataclass(frozen=True)
class SeparatedChanges:
    """
    A pull request's changes, told apart into those merges of its base branch made and
    those it made itself.
    """

    merged: tuple[FileVersions, ...]
    """
    The files only merges of the base branch changed.
    """

    own: PullRequestChanges
    """
    The pull request's own changes to every other file.
    """


# %% detection


@dataclass(frozen=True)
class BaseBranchMergeDetection:
    """
    Tells the files merges of a pull request's base branch changed from those it changed
    itself since the commit its changes are read from.
    """

    def separate(self, changes: PullRequestChanges) -> SeparatedChanges:
        """
        :param changes: A pull request and the files it changes since a commit.
        :return: Its files, its own changes read from that commit merged with its
            current merge base; every change its own when read from its merge base.
        """
        git = changes.commits.git
        start = changes.commits.base_commit
        head = changes.commits.head_commit
        base_branch = changes.pull_request.base.commit
        merge_base = git.merge_base(base_branch, head)
        if start == merge_base:
            return SeparatedChanges((), changes)
        reviewed_on_base = git.merge_commit(start, merge_base, REVIEWED_ON_BASE_MESSAGE)
        own_commits = CommitRange(git, reviewed_on_base.commit, head)
        own_versions = {
            file.path: file
            for file in own_commits.file_versions(
                frozenset(file.path for file in changes.files)
            )
        }
        own_change_at_start = CommitRange(
            git, git.merge_base(base_branch, start), start
        )
        own_change = CommitRange(git, merge_base, head)
        merged: list[FileVersions] = []
        own: list[FileVersions] = []
        for file in changes.files:
            if file.path not in reviewed_on_base.conflicted_paths:
                (own if file.path in own_versions else merged).append(
                    own_versions.get(file.path, file)
                )
            elif (
                file.previous_path is None
                and not file.is_binary
                and own_change.edited_lines(file.path)
                == own_change_at_start.edited_lines(file.path)
            ):
                merged.append(file)
            else:
                own.append(file)
        return SeparatedChanges(
            tuple(merged), replace(changes, commits=own_commits, files=tuple(own))
        )
