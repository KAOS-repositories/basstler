"""
Reading and searching the files of one commit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from pathlib import PurePosixPath

from basstler.exit_codes import ExitCode
from basstler.git.commands import GIT_TEXT_ENCODING, GitCommandRunner

# %% the files


class GitObjectMode(StrEnum):
    """
    The modes ``git ls-tree`` lists an entry with that the reading of a commit tells
    apart.
    """

    EXECUTABLE_FILE = "100755"
    """
    A file that is executable.
    """


class GitObjectType(StrEnum):
    """
    The types of the objects a tree lists.
    """

    BLOB = "blob"
    """
    A file's content.
    """


@dataclass(frozen=True)
class CommittedFile:
    """
    One file as a commit holds it.
    """

    content: bytes
    """
    The file's bytes.
    """

    is_executable: bool
    """
    Whether the commit holds the file as executable.
    """


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

    @cached_property
    def path_names(self) -> frozenset[str]:
        """
        The name of every directory and the stem of every file in the commit.

        :raises GitCommandFailed: If the listing fails.
        """
        return frozenset(
            name for path in self.file_paths for name in (*path.parent.parts, path.stem)
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

    def mentioned_words(self, words: frozenset[str]) -> frozenset[str]:
        """
        :param words: Names or any other fixed strings.
        :return: Those of *words* some file of the commit holds as a whole word, as
            :meth:`mentions` decides each.
        :raises GitCommandFailed: If a search itself fails.
        """
        named = words & self.path_names
        identifiers = frozenset(word for word in words - named if WORD.fullmatch(word))
        others = named | frozenset(
            word for word in words - named - identifiers if self.mentions(word)
        )
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

    @cached_property
    def committed_files(self) -> dict[PurePosixPath, CommittedFile]:
        """
        Every file of the commit, by its path from the commit's root.

        :raises GitCommandFailed: If git cannot list or read the commit.
        """
        entries = [
            entry.split("\t", 1)
            for entry in self.git.run_binary("ls-tree", "-r", "-z", self.commit)
            .decode(GIT_TEXT_ENCODING)
            .split("\0")
            if entry
        ]
        blobs = [
            (meta.split(), PurePosixPath(path))
            for meta, path in entries
            if meta.split()[1] == GitObjectType.BLOB
        ]
        contents = self.git.run_binary(
            "cat-file",
            "--batch",
            standard_input="".join(f"{fields[2]}\n" for fields, _ in blobs).encode(),
        )
        files = {}
        offset = 0
        for (mode, _, _), path in blobs:
            header_end = contents.index(b"\n", offset)
            size = int(contents[offset:header_end].split()[2])
            start = header_end + 1
            files[path] = CommittedFile(
                contents[start : start + size], mode == GitObjectMode.EXECUTABLE_FILE
            )
            offset = start + size + 1
        return files
