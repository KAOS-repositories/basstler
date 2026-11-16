"""
Tests for running git in a checkout.
"""

from __future__ import annotations

from pathlib import Path

from basstler.git.commands import GitCommandRunner

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


# %% committing files


def committing_repository(tmp_path: Path) -> GitCommandRunner:
    """
    :param tmp_path: An empty directory.
    :return: A repository there with an author configured.
    """
    git = GitCommandRunner(tmp_path)
    git.run("init", "--quiet")
    git.run("config", "user.name", "Test Author")
    git.run("config", "user.email", "author@example.com")
    return git


def test_committing_none_removes_the_file(tmp_path: Path) -> None:
    git = committing_repository(tmp_path)
    first = git.commit_files(None, {"kept.txt": "kept", "gone.txt": "gone"}, "Add")

    second = git.commit_files(first, {"gone.txt": None}, "Remove")

    assert git.run("ls-tree", "--name-only", second) == "kept.txt"


def test_a_copied_file_keeps_its_bytes_and_mode(tmp_path: Path) -> None:
    git = committing_repository(tmp_path)
    (tmp_path / "empty.py").write_bytes(b"")
    (tmp_path / "run.sh").write_bytes(b"echo")
    git.run("add", "empty.py", "run.sh")
    git.run("update-index", "--chmod=+x", "run.sh")
    git.run("commit", "--quiet", "-m", "Add")
    source = git.run("rev-parse", "HEAD")

    copied = git.commit_files(
        None, {}, "Copy", copied={"empty.py": source, "run.sh": source}
    )

    assert git.run("ls-tree", copied) == git.run("ls-tree", source)
