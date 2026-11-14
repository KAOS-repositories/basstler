"""
Detecting a definition moved from one module to another as a rename of its dotted path,
and triaging the imports that follow it.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import PurePosixPath

import pytest

from basstler.review_triage.comparison import MechanicalChange
from basstler.review_triage.definition_moves import DefinitionMoveDetection
from basstler.review_triage.pull_request import PullRequestChanges
from basstler.review_triage.renames import Rename, RenameDecisions
from basstler.review_triage.triage import PullRequestTriager

from ..scratch_repository import ScratchRepository
from .conftest import committed_pull_request
from .samples import DefinitionMoveFromMovedModuleSample, DefinitionMoveSample

# %% the sample


@pytest.fixture
def definition_move(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The sample moving definitions between modules, committed.
    """
    return committed_pull_request(
        scratch_repository,
        DefinitionMoveSample.BASE_TREE,
        DefinitionMoveSample.HEAD_TREE,
    )


@pytest.fixture
def definition_move_from_moved_module(
    scratch_repository: ScratchRepository,
) -> PullRequestChanges:
    """
    :return: The sample moving a class out of a module it also moves, committed.
    """
    return committed_pull_request(
        scratch_repository,
        DefinitionMoveFromMovedModuleSample.BASE_TREE,
        DefinitionMoveFromMovedModuleSample.HEAD_TREE,
    )


MOVED_IN_MODULE = PurePosixPath("package/priority.py")
"""
The module the definition-move sample adds, holding only a class moved into it.
"""


def with_moved_in_module(
    changes: PullRequestChanges, head_text: str
) -> PullRequestChanges:
    """
    :param changes: The definition-move sample.
    :param head_text: Another head version of :data:`MOVED_IN_MODULE`.
    :return: The sample with that version in place of the committed one.
    """
    return replace(
        changes,
        files=tuple(
            replace(change, head_text=head_text)
            if change.path == MOVED_IN_MODULE
            else change
            for change in changes.files
        ),
    )


# %% detection


def test_a_moved_definition_is_a_rename_of_its_dotted_path(
    definition_move: PullRequestChanges,
):
    """
    A class moved out of a module that stays is renamed to its path in the module that
    now defines it, whether that module existed before or is new.
    """
    assert DefinitionMoveDetection().decisions(definition_move) == RenameDecisions(
        (
            Rename(
                "package.board.Field",
                "package.record.Field",
                DefinitionMoveDetection.label,
            ),
            Rename(
                "package.board.Priority",
                "package.priority.Priority",
                DefinitionMoveDetection.label,
            ),
        )
    )


def test_imports_following_a_moved_definition_are_mechanical(
    definition_move: PullRequestChanges,
):
    """
    A file importing the moved classes from their new modules changes only its imports,
    and the modules they move between change only by losing or receiving them.
    """
    triage = PullRequestTriager().triage(definition_move)
    assert {file.change.path: file.kinds for file in triage.mechanical_files} == {
        PurePosixPath("caller.py"): frozenset({MechanicalChange.IMPORTS}),
        PurePosixPath("package/board.py"): frozenset(
            {MechanicalChange.DEFINITIONS_MOVED_OUT}
        ),
        PurePosixPath("package/record.py"): frozenset(
            {MechanicalChange.DEFINITIONS_MOVED_IN, MechanicalChange.IMPORTS}
        ),
        MOVED_IN_MODULE: frozenset({MechanicalChange.DEFINITIONS_MOVED_IN}),
    }


def test_a_definition_leaving_a_moved_module_is_a_rename_of_its_dotted_path(
    definition_move_from_moved_module: PullRequestChanges,
):
    """
    A class moved out of a module the pull request also moves is renamed from its path
    in the module's base version.
    """
    assert DefinitionMoveDetection().decisions(
        definition_move_from_moved_module
    ) == RenameDecisions(
        (
            Rename(
                "package.old_home.Route",
                "package.route.Route",
                DefinitionMoveDetection.label,
            ),
        )
    )


def test_a_new_module_of_definitions_moved_out_of_a_moved_module_is_mechanical(
    definition_move_from_moved_module: PullRequestChanges,
):
    """
    The moved module losing the class, the module receiving it with a docstring and a
    section header of its own, and the file importing it from there, are mechanical.
    """
    triage = PullRequestTriager().triage(definition_move_from_moved_module)
    assert {file.change.path: file.kinds for file in triage.mechanical_files} == {
        PurePosixPath("caller.py"): frozenset({MechanicalChange.IMPORTS}),
        PurePosixPath("package/new_home.py"): frozenset(
            {MechanicalChange.DEFINITIONS_MOVED_OUT, MechanicalChange.MOVE}
        ),
        PurePosixPath("package/route.py"): frozenset(
            {MechanicalChange.DEFINITIONS_MOVED_IN}
        ),
    }


# %% what a received definition may not change


@pytest.mark.parametrize(
    "head_text",
    [
        pytest.param(
            DefinitionMoveSample.HEAD_TREE.path.joinpath(MOVED_IN_MODULE)
            .read_text()
            .replace('"high"', '"urgent"'),
            id="definition-changed",
        ),
        pytest.param(
            DefinitionMoveSample.HEAD_TREE.path.joinpath(MOVED_IN_MODULE)
            .read_text()
            .replace("from enum import", "from other_enum import"),
            id="import-bound-elsewhere",
        ),
        pytest.param(
            DefinitionMoveSample.HEAD_TREE.path.joinpath(MOVED_IN_MODULE).read_text()
            + "\n\nLIMIT = 3\n",
            id="code-of-its-own",
        ),
    ],
)
def test_a_module_receiving_a_definition_and_more_needs_review(
    definition_move: PullRequestChanges, head_text: str
):
    """
    A module receiving a moved class needs review once anything else changes in it:
    the class itself, what its imports bind, or code it adds.
    """
    triage = PullRequestTriager().triage(
        with_moved_in_module(definition_move, head_text)
    )
    assert MOVED_IN_MODULE in {file.change.path for file in triage.files_needing_review}
