"""
Tests for :mod:`basstler.git.commit_tree`: reading and searching the files of one
commit.
"""

from __future__ import annotations

import stat
from pathlib import Path, PurePosixPath

import pytest

from basstler.git.commands import GitCommandRunner
from basstler.git.commit_tree import CommitTree, CommittedFile

from .test_commands import committed_repository

COMMITTED = {
    PurePosixPath("notes.txt"): CommittedFile(b"plain text\n", is_executable=False),
    PurePosixPath("bin/run.sh"): CommittedFile(b"echo run\n", is_executable=True),
    PurePosixPath("data/blob.bin"): CommittedFile(b"\x00\xff\x00", is_executable=False),
}
"""
The files :func:`committed_tree` commits, by path.
"""

# %% a commit's files


@pytest.fixture
def committed_tree(tmp_path: Path) -> CommitTree:
    """
    :return: A commit of :data:`COMMITTED` in a new repository.
    """
    git = GitCommandRunner(tmp_path)
    git.run("init", "--quiet")
    git.run("config", "user.name", "Test Author")
    git.run("config", "user.email", "author@example.com")
    for path, file in COMMITTED.items():
        written = tmp_path / path
        written.parent.mkdir(parents=True, exist_ok=True)
        written.write_bytes(file.content)
        if file.is_executable:
            written.chmod(written.stat().st_mode | stat.S_IXUSR)
    git.run("add", "--all")
    git.run("commit", "--quiet", "-m", "Commit the files")
    return CommitTree(git, git.commit_at("HEAD"))


def test_every_file_of_a_commit_is_read_with_its_bytes_and_mode(
    committed_tree: CommitTree,
):
    assert committed_tree.committed_files == COMMITTED


def test_a_git_command_s_output_is_read_as_bytes(committed_tree: CommitTree):
    blob = COMMITTED[PurePosixPath("data/blob.bin")]

    assert (
        committed_tree.git.run_binary("show", f"{committed_tree.commit}:data/blob.bin")
        == blob.content
    )


# %% the files a commit holds


@pytest.mark.parametrize(
    ("path", "held"),
    [("package/__init__.py", True), ("package", False), ("absent.py", False)],
)
def test_a_commit_holds_only_its_files(tmp_path: Path, path: str, held: bool):
    """
    A commit holds a file at the path of each of its files, not at a directory's.
    """
    git, commit = committed_repository(tmp_path, {"package/__init__.py": ""})

    assert CommitTree(git, commit).holds(PurePosixPath(path)) is held
