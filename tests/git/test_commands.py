"""
Tests for running git in a checkout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.git.commands import GitCommandFailed, GitCommandRunner

from ..constants.paths import DatasetLocation

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
