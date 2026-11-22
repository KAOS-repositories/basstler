"""
Searching the files of one commit.
"""

from __future__ import annotations

from dataclasses import dataclass

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
