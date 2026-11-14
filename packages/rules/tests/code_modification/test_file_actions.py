"""
Tests for :mod:`basstler.code_modification.file_actions` and
:mod:`basstler.code_modification.source_tree`: moving, creating and deleting files of a
source tree, and writing a tree to disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.code_modification.exceptions import (
    FileActionTargetError,
    FileExpectation,
)
from basstler.code_modification.file_actions import (
    FileCreation,
    FileDeletion,
    FileMove,
)
from basstler.code_modification.source_tree import SourceTree

from basstler_testing.constants.paths import RelocationTree

# %% the tree changed


@pytest.fixture
def before() -> SourceTree:
    """
    :return: The package whose tests import its helper and a sibling.
    """
    return SourceTree.of_directory(RelocationTree.BEFORE)


HELPER = Path("project/helper.py")
"""
The package's helper, in :func:`before`.
"""

SIBLING = Path("project/tests/sibling.py")
"""
The sibling of the package's tests, in :func:`before`.
"""


# %% moving a file


def test_a_moved_file_keeps_its_content_at_its_new_path(before):
    """
    The file is gone from where it was and holds the same bytes where it went.
    """
    moved = FileMove(HELPER, Path("helper.py")).apply(before).result

    assert (HELPER in moved.files, moved.files[Path("helper.py")]) == (
        False,
        before.files[HELPER],
    )


def test_a_move_of_a_missing_file_is_refused(before):
    """
    A move names a file the tree must hold.
    """
    with pytest.raises(FileActionTargetError) as raised:
        FileMove(Path("missing.py"), Path("helper.py")).apply(before)

    assert raised.value.expectation is FileExpectation.PRESENT


def test_a_move_onto_an_existing_file_is_refused(before):
    """
    A move never overwrites a file.
    """
    with pytest.raises(FileActionTargetError) as raised:
        FileMove(HELPER, SIBLING).apply(before)

    assert raised.value.expectation is FileExpectation.ABSENT


# %% creating and deleting a file


def test_a_creation_is_undone_by_deleting_the_file(before):
    """
    Creating a file and applying the inverse gives back the tree created in.
    """
    applied = FileCreation(Path("new.py"), b"").apply(before)

    assert applied.inverse.apply(applied.result).result == before


def test_a_deletion_of_other_content_is_refused(before):
    """
    A deletion names the content it removes, so its inverse can create it again.
    """
    with pytest.raises(FileActionTargetError) as raised:
        FileDeletion(HELPER, b"other").apply(before)

    assert raised.value.expectation is FileExpectation.CONTENT


# %% writing a tree to disk


def test_a_tree_written_over_another_is_what_the_directory_holds(before, tmp_path):
    """
    Writing the relocated tree over the original leaves the directory holding exactly
    the relocated tree.
    """
    before.write(tmp_path, SourceTree({}))
    moved = FileMove(HELPER, Path("helper.py")).apply(before).result

    moved.write(tmp_path, before)

    assert SourceTree.of_directory(tmp_path) == moved


def test_a_directory_a_write_empties_is_removed(before, tmp_path):
    """
    Writing the empty tree over one leaves no directory behind.
    """
    before.write(tmp_path, SourceTree({}))

    SourceTree({}).write(tmp_path, before)

    assert list(tmp_path.iterdir()) == []
