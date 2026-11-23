"""
Searching the files of one commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
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
    The files of one commit, searched for words.
    """

    git: GitCommandRunner
    """
    The checkout holding the commit.
    """

    commit: str
    """
    The commit searched.
    """

    @cached_property
    def path_names(self) -> frozenset[str]:
        """
        The name of every directory and the stem of every file in the commit.

        :raises GitCommandFailed: If listing the files fails.
        """
        paths = self.git.run("ls-tree", "-r", "--name-only", self.commit).splitlines()
        return frozenset(
            name
            for path in map(PurePosixPath, paths)
            for name in (*path.parent.parts, path.stem)
        )

    def mentions(self, word: str) -> bool:
        """
        :param word: A name or any other fixed string.
        :return: Whether any file of the commit holds it as a whole word, or one of
            :attr:`path_names` is it.
        :raises GitCommandFailed: If the search itself fails.
        """
        if word in self.path_names:
            return True
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
