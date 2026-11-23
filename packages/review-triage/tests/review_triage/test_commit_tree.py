"""
Tests for searching the Python modules of one commit for the classes inheriting from a
class.
"""

from __future__ import annotations

import pytest

from basstler.git.commit_tree import CommitTree
from basstler.review_triage.commit_tree import CommitModules
from basstler.review_triage.calls import ClassTarget, ReachableDefinition
from basstler.review_triage.definitions import DefinitionIndex
from basstler.review_triage.signatures import SignatureReader

from basstler_testing.constants.paths import DatasetLocation
from basstler_testing.scratch_repository import ScratchRepository

BASE_CLASS = "Shape"
"""
The class of the dataset whose subclasses are looked for.
"""

CONFLICTED_MODULE_NAME = "triangle.py"
"""
The name the conflicted subclass's module is committed under.
"""

# %% fixtures


def committed_class_headers(
    repository: ScratchRepository, modules: dict[str, str]
) -> CommitModules:
    """
    :param repository: The repository to commit in.
    :param modules: Further modules to commit, by file name.
    :return: The modules of a commit holding the class header dataset and those
        modules.
    """
    for module in DatasetLocation.CLASS_HEADERS.iterdir():
        repository.write(module.name, module.read_text(encoding="utf-8"))
    for name, text in modules.items():
        repository.write(name, text)
    repository.commit_everything("Add the classes")
    return CommitModules(CommitTree(repository.git, repository.git.commit_at("HEAD")))


@pytest.fixture
def class_headers(scratch_repository: ScratchRepository) -> CommitModules:
    """
    :return: The modules of a commit holding the class header dataset.
    """
    return committed_class_headers(scratch_repository, {})


@pytest.fixture
def conflicted_class_headers(scratch_repository: ScratchRepository) -> CommitModules:
    """
    :return: The modules of a commit holding the class header dataset and a subclass a
        merge left conflicted.
    """
    return committed_class_headers(
        scratch_repository,
        {
            CONFLICTED_MODULE_NAME: DatasetLocation.CONFLICTED_MODULE.read_text(
                encoding="utf-8"
            )
        },
    )


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


# %% a module that does not parse


def test_a_class_a_module_that_does_not_parse_defines_has_no_known_definition(
    conflicted_class_headers: CommitModules,
):
    """
    A name a module that does not parse defines is reported without definitions, never
    with only those of the modules that parse.
    """
    assert DefinitionIndex(conflicted_class_headers).definitions_of("Triangle") == ()


def test_a_hierarchy_reaching_a_module_that_does_not_parse_is_unreadable(
    conflicted_class_headers: CommitModules,
):
    """
    A class one of whose subclasses may be defined in a module that does not parse has a
    hierarchy that cannot be read; a subclass whose own hierarchy avoids that module
    can.
    """
    index = DefinitionIndex(conflicted_class_headers)

    assert (index.reads_hierarchy_of("Shape"), index.reads_hierarchy_of("Circle")) == (
        False,
        True,
    )


def test_a_class_whose_hierarchy_cannot_be_read_has_an_unreadable_signature(
    conflicted_class_headers: CommitModules,
):
    """
    Making an instance of a class one of whose subclasses may be defined in a module
    that does not parse reaches a signature that cannot be read.
    """
    reader = SignatureReader(DefinitionIndex(conflicted_class_headers))

    assert ClassTarget(BASE_CLASS).reachable_definitions(reader) == [
        ReachableDefinition(BASE_CLASS, None)
    ]
