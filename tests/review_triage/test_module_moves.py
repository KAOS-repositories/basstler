"""
Detecting a moved module as a rename of its dotted path, and triaging the imports that
follow it.
"""

from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from basstler.review_triage.comparison import MechanicalChange
from basstler.review_triage.module_moves import ModuleMoveDetection
from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.renames import Rename, RenameDecisions
from basstler.review_triage.triage import PullRequestTriager

from ..scratch_repository import ScratchRepository
from .conftest import committed_pull_request
from .samples import (
    AmbiguousPackageInitializersSample,
    ModuleMoveSample,
    PackageRootMoveSample,
)

# %% the sample


@pytest.fixture
def module_move(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The sample moving a module, committed to a scratch repository.
    """
    return committed_pull_request(
        scratch_repository, ModuleMoveSample.BASE_TREE, ModuleMoveSample.HEAD_TREE
    )


# %% detection


def test_a_moved_module_is_a_rename_of_its_dotted_path(
    module_move: PullRequestChanges,
):
    """
    A module moved into a subpackage is renamed from its old dotted path to its new one.
    """
    assert ModuleMoveDetection().decisions(module_move) == RenameDecisions(
        (
            Rename(
                "package.repository",
                "package.storage.repository",
                ModuleMoveDetection(),
            ),
        )
    )


def test_imports_following_a_moved_module_are_mechanical(
    module_move: PullRequestChanges,
):
    """
    A file importing the moved module from its new path changes only its imports.
    """
    triage = PullRequestTriager().triage(module_move)
    assert {file.change.path: file.kinds for file in triage.mechanical_files} == {
        PurePosixPath("caller.py"): frozenset({MechanicalChange.IMPORTS}),
        PurePosixPath("package/storage/repository.py"): frozenset(
            {MechanicalChange.MOVE}
        ),
    }


# %% a package moved under a directory that is not a package


def test_a_package_moved_under_a_plain_directory_keeps_its_relative_imports_mechanical(
    scratch_repository: ScratchRepository,
):
    """
    Moving a package whole leaves its dotted paths unchanged, so a relative import of a
    sibling module still reaches the same module.
    """
    changes = committed_pull_request(
        scratch_repository,
        PackageRootMoveSample.BASE_TREE,
        PackageRootMoveSample.HEAD_TREE,
    )
    triage = PullRequestTriager().triage(changes)
    assert triage.files_needing_review == ()


# %% empty package initializers git cannot tell apart


def test_empty_package_initializers_paired_by_git_do_not_rename_their_packages(
    scratch_repository: ScratchRepository,
):
    """
    Git pairs identical, empty ``__init__.py`` files in no meaningful order, so a package
    is not renamed to the package of the file git paired its initializer with.
    """
    changes = committed_pull_request(
        scratch_repository,
        AmbiguousPackageInitializersSample.BASE_TREE,
        AmbiguousPackageInitializersSample.HEAD_TREE,
    )
    assert ModuleMoveDetection().decisions(changes) == RenameDecisions(())
