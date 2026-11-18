"""
Searching the files of one commit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import PurePosixPath

from basstler.exit_codes import ExitCode
from basstler.git.commands import GitCommandRunner

# %% the search

PATH_TERMINATOR = "\0"
"""
What ``git ls-tree -z`` ends each path it lists with.
"""

WORD = re.compile(r"\w+", re.ASCII)
"""
A run of the characters ``git grep --word-regexp`` counts as part of a word, which a
regular expression matches literally: whole-word matches of two such runs never overlap,
so one search for their alternation finds each a search for it alone finds.
"""


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

    @cached_property
    def file_paths(self) -> frozenset[PurePosixPath]:
        """
        The path of every file of the commit, from its root, listed by one command.

        :raises GitCommandFailed: If the listing fails.
        """
        listing = self.git.run("ls-tree", "-r", "--name-only", "-z", self.commit)
        return frozenset(
            PurePosixPath(path) for path in listing.split(PATH_TERMINATOR) if path
        )

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

    def mentioned_words(self, words: frozenset[str]) -> frozenset[str]:
        """
        :param words: Names or any other fixed strings.
        :return: Those of *words* some file of the commit holds as a whole word, as
            :meth:`mentions` decides each.
        :raises GitCommandFailed: If a search itself fails.
        """
        identifiers = frozenset(word for word in words if WORD.fullmatch(word))
        others = frozenset(word for word in words - identifiers if self.mentions(word))
        if not identifiers:
            return others
        search = self.git.attempt(
            "grep",
            "--only-matching",
            "-h",
            "--word-regexp",
            "--extended-regexp",
            "-f",
            "-",
            self.commit,
            standard_input=f"{'|'.join(sorted(identifiers))}\n",
        )
        if search.exit_status == GitGrepExitCode.NO_MATCH:
            return others
        return others | (
            frozenset(search.raise_if_failed().output.splitlines()) & identifiers
        )

    def holds(self, path: PurePosixPath) -> bool:
        """
        :param path: A path from the commit's root.
        :return: Whether the commit has a file there.
        """
        return path in self.file_paths
