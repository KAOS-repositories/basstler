"""
Tests for searching the Python modules of one commit for the classes inheriting from a
class.
"""

from __future__ import annotations

import pytest

from basstler.git.commit_tree import CommitTree
from basstler.review_triage.commit_tree import CommitModules
from basstler.review_triage.definitions import DefinitionIndex

from ..constants.paths import DatasetLocation
from ..scratch_repository import ScratchRepository

BASE_CLASS = "Shape"
"""
The class of the dataset whose subclasses are looked for.
"""

# %% fixtures


@pytest.fixture
def class_headers(scratch_repository: ScratchRepository) -> CommitModules:
    """
    :return: The modules of a commit holding the class header dataset.
    """
    for module in DatasetLocation.CLASS_HEADERS.iterdir():
        scratch_repository.write(module.name, module.read_text(encoding="utf-8"))
    scratch_repository.commit_everything("Add the classes")
    git = scratch_repository.git
    return CommitModules(CommitTree(git, git.commit_at("HEAD")))


# %% the classes inheriting from a class


def test_the_files_subclassing_a_class_are_those_naming_it_among_their_bases(
    class_headers: CommitModules,
):
    """
    A file naming the class among the bases of one of its classes is found, whether on
    the line defining the class or after it; a file only mentioning the class is not.
    """
    commit = class_headers.tree.commit

    found = class_headers.files_subclassing(BASE_CLASS)

    assert set(found) == {f"{commit}:circle.py", f"{commit}:square.py"}


def test_every_subclass_of_a_commit_is_found(class_headers: CommitModules):
    """
    The classes of a commit inheriting from a class are found wherever their bases are
    written.
    """
    found = DefinitionIndex(class_headers).subclasses_of(BASE_CLASS)

    assert {definition.name for definition in found} == {"Circle", "Square"}
