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
from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.renames import MemberRename, Rename, RenameDecisions
from basstler.review_triage.triage import PullRequestTriager

from basstler_testing.scratch_repository import ScratchRepository
from .conftest import committed_pull_request
from .samples import (
    DefinitionMoveAgainstRenameSample,
    DefinitionMoveAndRenameSample,
    DefinitionMoveNamespacePackageSample,
    DefinitionMovePackageRootSample,
    DefinitionMoveSameModulePathSample,
    SECTIONED_BOARD,
    DefinitionMoveFromMovedModuleSample,
    DefinitionMoveSample,
    ModuleSplitSample,
    DocumentedConstantMoveSample,
)
from basstler.text_file import TextFile

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


SOURCE_MODULE = PurePosixPath("package/board.py")
"""
The module of the definition-move sample that classes move out of.
"""


def with_source_module(
    changes: PullRequestChanges, base_text: str, head_text: str
) -> PullRequestChanges:
    """
    :param changes: The definition-move sample.
    :param base_text: Another base version of :data:`SOURCE_MODULE`.
    :param head_text: Another head version of it.
    :return: The sample with those versions in place of the committed ones.
    """
    return replace(
        changes,
        files=tuple(
            replace(change, base_text=base_text, head_text=head_text)
            if change.path == SOURCE_MODULE
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
                DefinitionMoveDetection(),
            ),
            Rename(
                "package.board.Priority",
                "package.priority.Priority",
                DefinitionMoveDetection(),
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
                DefinitionMoveDetection(),
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


@pytest.mark.parametrize(
    "versions",
    [
        pytest.param(("board_base.py", "board_head.py"), id="section-kept"),
        pytest.param(
            ("board_base.py", "board_header_dropped_head.py"), id="header-dropped"
        ),
        pytest.param(
            ("board_emptied_section_base.py", "board_emptied_section_head.py"),
            id="section-emptied",
        ),
        pytest.param(
            ("board_emptied_section_base.py", "board_emptied_header_left_head.py"),
            id="emptied-header-left",
        ),
    ],
)
def test_a_section_header_above_definitions_moving_out_may_stay_or_go(
    definition_move: PullRequestChanges, versions: tuple[str, str]
):
    """
    A section header above definitions that move out leaves with them when they were all
    its section held, and otherwise may stay or go.
    """
    base_name, head_name = versions
    triage = PullRequestTriager().triage(
        with_source_module(
            definition_move,
            TextFile(SECTIONED_BOARD / base_name).read(),
            TextFile(SECTIONED_BOARD / head_name).read(),
        )
    )
    assert {file.change.path: file.kinds for file in triage.mechanical_files}[
        SOURCE_MODULE
    ] == frozenset({MechanicalChange.DEFINITIONS_MOVED_OUT})


# %% what a received definition may not change


@pytest.mark.parametrize(
    "head_text",
    [
        pytest.param(
            TextFile(DefinitionMoveSample.HEAD_TREE.path.joinpath(MOVED_IN_MODULE))
            .read()
            .replace('"high"', '"urgent"'),
            id="definition-changed",
        ),
        pytest.param(
            TextFile(DefinitionMoveSample.HEAD_TREE.path.joinpath(MOVED_IN_MODULE))
            .read()
            .replace("from enum import", "from other_enum import"),
            id="import-bound-elsewhere",
        ),
        pytest.param(
            TextFile(
                DefinitionMoveSample.HEAD_TREE.path.joinpath(MOVED_IN_MODULE)
            ).read()
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


# %% a package kept under a directory that is not a package


def test_relative_imports_following_a_moved_definition_are_mechanical(
    scratch_repository: ScratchRepository,
):
    """
    A relative import of a moved class follows it, though the package sits under a
    directory that is not itself a package.
    """
    changes = committed_pull_request(
        scratch_repository,
        DefinitionMovePackageRootSample.BASE_TREE,
        DefinitionMovePackageRootSample.HEAD_TREE,
    )
    assert PullRequestTriager().triage(changes).files_needing_review == ()


def test_a_definition_moved_within_a_namespace_package_is_a_rename_of_its_path(
    scratch_repository: ScratchRepository,
):
    """
    A class moved between two projects sharing a namespace package is renamed by its
    dotted path below the namespace package, as it is imported.
    """
    changes = committed_pull_request(
        scratch_repository,
        DefinitionMoveNamespacePackageSample.BASE_TREE,
        DefinitionMoveNamespacePackageSample.HEAD_TREE,
    )
    detection = DefinitionMoveDetection()
    assert detection.decisions(changes) == RenameDecisions(
        (
            Rename(
                "tool.locations.CommitScratchFile",
                "tool.git.locations.CommitScratchFile",
                detection,
            ),
        )
    )


def test_the_imports_following_a_move_within_a_namespace_package_are_mechanical(
    scratch_repository: ScratchRepository,
):
    """
    Each module of the move, and the module importing the class from its new place, is
    mechanical.
    """
    changes = committed_pull_request(
        scratch_repository,
        DefinitionMoveNamespacePackageSample.BASE_TREE,
        DefinitionMoveNamespacePackageSample.HEAD_TREE,
    )
    triage = PullRequestTriager().triage(changes)
    assert {file.change.path: file.kinds for file in triage.mechanical_files} == {
        PurePosixPath("core/src/tool/locations.py"): frozenset(
            {MechanicalChange.DEFINITIONS_MOVED_OUT}
        ),
        PurePosixPath("git/src/tool/git/locations.py"): frozenset(
            {MechanicalChange.DEFINITIONS_MOVED_IN}
        ),
        PurePosixPath("git/src/tool/git/commands.py"): frozenset(
            {MechanicalChange.IMPORTS}
        ),
    }


def test_a_definition_moved_between_files_of_one_dotted_path_is_mechanical(
    scratch_repository: ScratchRepository,
):
    """
    A function moved into a new file whose dotted path is the old file's leaves the old
    file reduced and the new one holding it, without either being mistaken for the
    other.
    """
    changes = committed_pull_request(
        scratch_repository,
        DefinitionMoveSameModulePathSample.BASE_TREE,
        DefinitionMoveSameModulePathSample.HEAD_TREE,
    )
    triage = PullRequestTriager().triage(changes)
    assert {file.change.path: file.kinds for file in triage.mechanical_files} == {
        PurePosixPath("tests/plan/conftest.py"): frozenset(
            {MechanicalChange.DEFINITIONS_MOVED_OUT}
        ),
        PurePosixPath("packages/tool/tests/plan/conftest.py"): frozenset(
            {MechanicalChange.DEFINITIONS_MOVED_IN}
        ),
    }


# %% a definition carried on under another name


def test_a_definition_of_the_old_name_elsewhere_is_no_move_of_a_renamed_one(
    scratch_repository: ScratchRepository,
):
    """
    A class renamed in its module is no move to another module adding a class of its old
    name that its code does not carry on.
    """
    changes = committed_pull_request(
        scratch_repository,
        DefinitionMoveAgainstRenameSample.BASE_TREE,
        DefinitionMoveAgainstRenameSample.HEAD_TREE,
    )
    assert DefinitionMoveDetection().decisions(changes) == RenameDecisions(())


def test_the_files_following_an_in_place_rename_beside_a_new_namesake_are_mechanical(
    scratch_repository: ScratchRepository,
):
    """
    The module renaming the class and the file using it by its new name are mechanical;
    the module adding a class of the old name is not.
    """
    changes = committed_pull_request(
        scratch_repository,
        DefinitionMoveAgainstRenameSample.BASE_TREE,
        DefinitionMoveAgainstRenameSample.HEAD_TREE,
    )
    triage = PullRequestTriager().triage(changes)
    assert {file.change.path: file.kinds for file in triage.mechanical_files} == {
        PurePosixPath("caller.py"): frozenset({MechanicalChange.RENAME}),
        PurePosixPath("package/geometry.py"): frozenset({MechanicalChange.RENAME}),
    }
    assert {file.change.path for file in triage.files_needing_review} == {
        PurePosixPath("package/pose.py")
    }


def test_a_definition_moved_under_a_new_name_is_a_rename_of_its_dotted_path(
    scratch_repository: ScratchRepository,
):
    """
    A class moved to another module under a new name its uses take on is renamed to its
    path there.
    """
    changes = committed_pull_request(
        scratch_repository,
        DefinitionMoveAndRenameSample.BASE_TREE,
        DefinitionMoveAndRenameSample.HEAD_TREE,
    )
    detection = DefinitionMoveDetection()
    assert detection.decisions(changes) == RenameDecisions(
        (
            MemberRename(
                "package.shapes.Square", "package.polygons.RegularSquare", detection
            ),
        )
    )


def test_the_files_of_a_definition_moved_under_a_new_name_are_mechanical(
    scratch_repository: ScratchRepository,
):
    """
    The module the class leaves, the module receiving it renamed, and the file importing
    it by its new name from there are mechanical.
    """
    changes = committed_pull_request(
        scratch_repository,
        DefinitionMoveAndRenameSample.BASE_TREE,
        DefinitionMoveAndRenameSample.HEAD_TREE,
    )
    assert PullRequestTriager().triage(changes).files_needing_review == ()


# %% a module split into several


@pytest.fixture
def module_split(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The sample splitting a module into several, committed.
    """
    return committed_pull_request(
        scratch_repository, ModuleSplitSample.BASE_TREE, ModuleSplitSample.HEAD_TREE
    )


def test_a_definition_renamed_as_it_moves_out_of_a_split_module_is_found(
    module_split: PullRequestChanges,
):
    """
    A class moved and renamed is a rename of its dotted path, though only the code of a
    definition moving with it uses the new name.
    """
    detection = DefinitionMoveDetection()
    assert detection.decisions(module_split) == RenameDecisions(
        (
            Rename("package.storage.ROW_LIMIT", "package.limits.ROW_LIMIT", detection),
            Rename("package.storage.Reader", "package.reading.Reader", detection),
            MemberRename(
                "package.storage._SessionKey", "package.sessions.SessionKey", detection
            ),
        )
    )


def test_the_modules_a_module_is_split_into_are_mechanical(
    module_split: PullRequestChanges,
):
    """
    The split module, each module it is split into and the file importing from them are
    mechanical, an assignment moving with the docstring below it.
    """
    assert PullRequestTriager().triage(module_split).files_needing_review == ()


# %% a documented assignment moved


def test_a_moved_constant_takes_its_docstring_along(
    scratch_repository: ScratchRepository,
):
    """
    The module a documented constant leaves, the module it moves into and the file
    importing it from there are mechanical.
    """
    changes = committed_pull_request(
        scratch_repository,
        DocumentedConstantMoveSample.BASE_TREE,
        DocumentedConstantMoveSample.HEAD_TREE,
    )
    assert PullRequestTriager().triage(changes).files_needing_review == ()
