"""
Tests for searching the files of one commit.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from basstler.git.commit_tree import CommitTree

from .test_commands import committed_repository

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
