"""
The files changed between two commits, each in both its versions.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import PurePosixPath

from basstler.git.commands import GitCommandRunner
from basstler.git.commit_tree import CommitTree

# %% one file's change


@dataclass(frozen=True)
class FileChange:
    """
    One file changed between two commits, in both its versions.
    """

    path: PurePosixPath
    """
    Where the file is in the head commit, or was in the base commit when it is deleted.
    """

    base_text: str | None
    """
    The file's content in the base commit, ``None`` when it is added or binary.
    """

    head_text: str | None
    """
    The file's content in the head commit, ``None`` when it is deleted or binary.
    """

    previous_path: PurePosixPath | None = None
    """
    Where the file was in the base commit, when the change moves it.
    """

    is_binary: bool = False
    """
    Whether git compares the file as binary, which leaves both texts unread.
    """


# %% the changed files


@dataclass(frozen=True)
class CommitRange:
    """
    The change from a base commit to a head commit.
    """

    git: GitCommandRunner
    """
    The checkout holding both commits.
    """

    base_commit: str
    """
    The commit the change starts from.
    """

    head_commit: str
    """
    The commit the change ends at.
    """

    @cached_property
    def base_tree(self) -> CommitTree:
        """
        The files of :attr:`base_commit`.
        """
        return CommitTree(self.git, self.base_commit)

    @cached_property
    def head_tree(self) -> CommitTree:
        """
        The files of :attr:`head_commit`.
        """
        return CommitTree(self.git, self.head_commit)

    def changes(self) -> tuple[FileChange, ...]:
        """
        :return: Every file the range changes, in the order git lists them.
        """
        listing = iter(
            self.git.run(
                "diff",
                "--numstat",
                "-z",
                "--find-renames",
                self.base_commit,
                self.head_commit,
            ).split("\0")
        )
        changes: list[FileChange] = []
        for entry in listing:
            if not entry:
                continue
            added, _, path = entry.split("\t", 2)
            previous_path = None
            if not path:
                previous_path = PurePosixPath(next(listing))
                path = next(listing)
            changes.append(
                self.change(PurePosixPath(path), previous_path, added == "-")
            )
        return tuple(changes)

    def change(
        self, path: PurePosixPath, previous_path: PurePosixPath | None, is_binary: bool
    ) -> FileChange:
        """
        :param path: Where the file is in the head commit.
        :param previous_path: Where it was in the base commit, when it moved.
        :param is_binary: Whether git compares it as binary.
        :return: The file's change, its texts read unless it is binary.
        """
        if is_binary:
            return FileChange(path, None, None, previous_path, is_binary)
        return FileChange(
            path,
            self.git.file_at(self.base_commit, previous_path or path),
            self.git.file_at(self.head_commit, path),
            previous_path,
        )
