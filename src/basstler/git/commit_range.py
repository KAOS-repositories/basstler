"""
The files changed between two commits, by how many lines and in both their versions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath

from basstler.git.commands import GitCommandRunner

# %% one file's change


@dataclass(frozen=True)
class FileChange:
    """
    One file changed between two commits, and by how many lines.
    """

    path: PurePosixPath
    """
    Where the file is in the head commit, or was in the base commit when it is deleted.
    """

    insertions: int = 0
    """
    Lines added, zero for a binary file.
    """

    deletions: int = 0
    """
    Lines removed, zero for a binary file.
    """

    previous_path: PurePosixPath | None = None
    """
    Where the file was in the base commit, when the change moves it.
    """

    is_binary: bool = False
    """
    Whether git compares the file as binary, which leaves its lines uncounted.
    """

    @property
    def changed_lines(self) -> int:
        """
        Lines added and removed together.
        """
        return self.insertions + self.deletions


@dataclass(frozen=True)
class FileVersions(FileChange):
    """
    A file's change, with the file's text in both commits.
    """

    base_text: str | None = None
    """
    The file's content in the base commit, ``None`` when it is added or binary.
    """

    head_text: str | None = None
    """
    The file's content in the head commit, ``None`` when it is deleted or binary.
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

    def file_changes(self) -> tuple[FileChange, ...]:
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
            insertions, deletions, path = entry.split("\t", 2)
            previous_path = None
            if not path:
                previous_path = PurePosixPath(next(listing))
                path = next(listing)
            is_binary = insertions == "-"
            changes.append(
                FileChange(
                    PurePosixPath(path),
                    0 if is_binary else int(insertions),
                    0 if is_binary else int(deletions),
                    previous_path,
                    is_binary,
                )
            )
        return tuple(changes)

    def file_versions(self) -> tuple[FileVersions, ...]:
        """
        :return: Every file the range changes, with its texts read unless it is binary.
        """
        return tuple(
            FileVersions(**asdict(change))
            if change.is_binary
            else FileVersions(
                **asdict(change),
                base_text=self.git.file_at(
                    self.base_commit, change.previous_path or change.path
                ),
                head_text=self.git.file_at(self.head_commit, change.path),
            )
            for change in self.file_changes()
        )
