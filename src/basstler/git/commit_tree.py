"""
Searching the files of one commit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from basstler.exit_codes import ExitCode
from basstler.git.commands import GitCommandRunner

# %% the search


class GitGrepExitCode(ExitCode):
    """
    What ``git grep`` exits with.
    """

    SUCCESS = 0
    """
    At least one line matched.
    """

    NO_MATCH = 1
    """
    Nothing matched.
    """


@dataclass(frozen=True)
class CommitTree:
    """
    The files of one commit, searched for words and paths.
    """

    git: GitCommandRunner
    """
    The checkout holding the commit.
    """

    commit: str
    """
    The commit searched.
    """

    held_paths: dict[PurePosixPath, bool] = field(
        default_factory=dict, compare=False, repr=False
    )
    """
    :meth:`holds` for each path asked about so far.
    """

    def mentions(self, word: str) -> bool:
        """
        :param word: A name or any other fixed string.
        :return: Whether any file of the commit holds it as a whole word.
        :raises GitCommandFailed: If the search itself fails.
        """
        search = self.git.attempt(
            "grep",
            "--quiet",
            "--word-regexp",
            "--fixed-strings",
            "-e",
            word,
            self.commit,
        )
        if search.exit_status == GitGrepExitCode.NO_MATCH:
            return False
        return search.raise_if_failed().succeeded

    def holds(self, path: PurePosixPath) -> bool:
        """
        :param path: A path from the commit's root.
        :return: Whether the commit has a file there.
        """
        if path not in self.held_paths:
            self.held_paths[path] = self.git.attempt(
                "cat-file", "-e", f"{self.commit}:{path}"
            ).succeeded
        return self.held_paths[path]
