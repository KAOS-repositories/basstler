"""
Tests for :mod:`basstler.directory_tree`: removing a directory and everything in it,
read-only entries included, as git leaves its object files on Windows.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.directory_tree import DirectoryTree

from basstler_testing.constants.environment import FileMode

# %% removal


def test_a_tree_holding_read_only_entries_is_removed(tmp_path: Path):
    """
    A read-only directory stands in for git's read-only object files: neither can be
    deleted from as it is, on Linux and on Windows respectively.
    """
    tree = tmp_path / "clone"
    objects = tree / ".git" / "objects"
    objects.mkdir(parents=True)
    (objects / "object").write_text("blob", encoding="utf-8")
    objects.chmod(FileMode.READ_ONLY_DIRECTORY)

    DirectoryTree(tree).remove()

    assert not tree.exists()


def test_removing_a_tree_that_is_not_there_does_nothing(tmp_path: Path):
    """
    A missing tree is no error.
    """
    before = sorted(tmp_path.iterdir())

    DirectoryTree(tmp_path / "never-made").remove()

    assert sorted(tmp_path.iterdir()) == before


# %% ignoring errors


def test_a_refusal_that_is_no_permission_error_is_raised_by_default(tmp_path: Path):
    """
    Without :attr:`DirectoryTree.ignore_errors`, a refusal making a tree writable does
    not cure is raised.
    """
    refusal = OSError("busy")
    removals: list[str] = []

    with pytest.raises(OSError) as raised:
        DirectoryTree(tmp_path).handle_refusal(removals.append, "entry", refusal)

    assert raised.value is refusal


def test_a_refusal_that_is_no_permission_error_is_ignored_when_errors_are(
    tmp_path: Path,
):
    """
    With :attr:`DirectoryTree.ignore_errors`, the entry that refuses is left in place.
    """
    removals: list[str] = []

    DirectoryTree(tmp_path, ignore_errors=True).handle_refusal(
        removals.append, "entry", OSError("busy")
    )

    assert removals == []


def test_a_tree_holding_read_only_entries_is_removed_when_errors_are_ignored(
    tmp_path: Path,
):
    """
    Ignoring errors still makes read-only entries writable, which is why the tree is
    removed rather than left.
    """
    tree = tmp_path / "clone"
    objects = tree / ".git" / "objects"
    objects.mkdir(parents=True)
    (objects / "object").write_text("blob", encoding="utf-8")
    objects.chmod(FileMode.READ_ONLY_DIRECTORY)

    DirectoryTree(tree, ignore_errors=True).remove()

    assert not tree.exists()
