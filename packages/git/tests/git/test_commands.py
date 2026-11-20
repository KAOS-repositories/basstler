"""
Tests for running git in a checkout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.git.commands import GitCommandFailed, GitCommandRunner
from basstler.git.commit_tree import CommitTree

from basstler_testing.constants.paths import DatasetLocation

# %% non-ASCII file contents


def test_file_round_trips_non_ascii_text(tmp_path: Path) -> None:
    git = GitCommandRunner(tmp_path)
    git.run("init", "--quiet")
    git.run("config", "user.name", "Test Author")
    git.run("config", "user.email", "author@example.com")
    text = DatasetLocation.NON_ASCII_TEXT.read_text(encoding="utf-8").rstrip("\n")

    commit = git.commit_files(None, {"notes.txt": text}, "Add notes")

    assert git.file_at(commit, "notes.txt") == text


# %% reading many files at once


def committed_repository(
    tmp_path: Path, files: dict[str, str]
) -> tuple[GitCommandRunner, str]:
    """
    :param tmp_path: Where the repository is made.
    :param files: The files of its one commit, by path.
    :return: The repository and its commit.
    """
    git = GitCommandRunner(tmp_path)
    git.run("init", "--quiet")
    git.run("config", "user.name", "Test Author")
    git.run("config", "user.email", "author@example.com")
    return git, git.commit_files(None, files, "Add files")


def test_object_texts_read_as_each_file_alone_would(tmp_path: Path) -> None:
    """
    Every file read together has the text it has when read on its own.
    """
    text = DatasetLocation.NON_ASCII_TEXT.read_text(encoding="utf-8")
    git, commit = committed_repository(
        tmp_path,
        {"notes.txt": text, "lines.txt": "first\r\nsecond\n\n", "empty.txt": ""},
    )
    names = tuple(
        f"{commit}:{path}" for path in ("notes.txt", "lines.txt", "empty.txt")
    )

    assert git.object_texts(names) == {name: git.run("show", name) for name in names}


def test_a_missing_object_fails_the_read(tmp_path: Path) -> None:
    """
    Naming a file the commit does not have is a failed git command.
    """
    git, commit = committed_repository(tmp_path, {"notes.txt": "notes"})

    with pytest.raises(GitCommandFailed):
        git.object_texts((f"{commit}:notes.txt", f"{commit}:absent.txt"))


def test_existing_object_texts_leave_out_a_missing_object(tmp_path: Path) -> None:
    """
    Naming a file the commit does not have leaves it out, the others read as alone.
    """
    git, commit = committed_repository(
        tmp_path, {"notes.txt": "notes", "lines.txt": "first\nsecond"}
    )
    present = (f"{commit}:notes.txt", f"{commit}:lines.txt")

    texts = git.existing_object_texts((present[0], f"{commit}:absent.txt", present[1]))

    assert texts == {name: git.run("show", name) for name in present}


# %% searching a commit for words


def test_mentioned_words_are_those_a_whole_word_search_finds(tmp_path: Path) -> None:
    """
    Of several words, those found are exactly those each search alone finds, a word only
    part of a longer one and a dotted path included.
    """
    git, commit = committed_repository(
        tmp_path,
        {
            "module.py": "from package.module import Name\nNameSuffix = Other\n",
            "notes.md": "Other and Third",
        },
    )
    tree = CommitTree(git, commit)
    words = frozenset(
        {"Name", "Name2", "Suffix", "Other", "Third", "package.module", "module.Name"}
    )

    assert tree.mentioned_words(words) == frozenset(
        word for word in words if tree.mentions(word)
    )
