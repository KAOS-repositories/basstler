"""
Tests for :mod:`basstler.code_rules.package_boundaries`: reporting imports of a
distribution the importing module's distribution does not list.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from basstler.code_rules.package_boundaries import (
    BoundaryCrossing,
    ModuleRenames,
    PackageAtCommit,
    PackageBoundaryChecker,
    PackageCrossings,
)
from basstler.package_map import Workspace

from basstler_testing.constants.paths import PackageBoundarySnippet

# %% the dataset's workspace


@pytest.fixture
def checker() -> PackageBoundaryChecker:
    """
    :return: A checker of the dataset's workspace.
    """
    return PackageBoundaryChecker(Workspace(PackageBoundarySnippet.DIRECTORY.value))


def violation_lines(checker: PackageBoundaryChecker, path: Path) -> list[int]:
    """
    :return: The first line of each violation *checker* reports in *path*.
    """
    return [violation.first_line for violation in checker.violations(path)]


# %% imports


def test_an_import_of_a_listed_distribution_is_not_reported(checker):
    """
    The higher distribution lists the lower one, so both its imports of it are allowed.
    """
    assert violation_lines(checker, PackageBoundarySnippet.LISTED_IMPORT) == []


def test_an_import_of_an_unlisted_distribution_is_reported(checker):
    """
    The lower distribution does not list the higher one.
    """
    import_line = 7

    assert violation_lines(checker, PackageBoundarySnippet.UNLISTED_IMPORT) == [
        import_line
    ]


def test_a_from_import_of_a_module_names_that_module(checker):
    """
    ``from basstler.high import caller`` imports the module ``high.caller``.
    """
    (crossing,) = checker.crossings(PackageBoundarySnippet.UNLISTED_IMPORT)

    assert crossing.imported_module == "high.caller"


# %% modules


def test_a_file_outside_the_package_is_not_checked(checker):
    """
    A test or a script belongs to no distribution.
    """
    assert violation_lines(checker, Path(__file__)) == []


# %% the package's crossings


def test_the_package_s_crossings_are_listed_by_module(checker):
    """
    The dataset's one crossing is the lower distribution's import of the higher one.
    """
    assert checker.package_crossings().crossings == (
        BoundaryCrossing(importing_module="low.upward", imported_module="high.caller"),
    )


def test_a_crossing_the_base_does_not_hold_is_new(checker):
    """
    Against a base with no crossings, every crossing of the package is new.
    """
    crossings = checker.package_crossings()

    assert crossings.added_since(PackageCrossings(crossings=())) == (
        crossings.crossings
    )


def test_a_crossing_the_base_holds_is_not_new(checker):
    """
    A crossing the base already had is left for the item that moves its code.
    """
    crossings = checker.package_crossings()

    assert crossings.added_since(crossings) == ()


# %% renamed modules


def test_a_crossing_the_base_holds_under_a_module_s_old_name_is_not_new(checker):
    """
    A module that moved keeps the crossings it had under its old name.
    """
    crossings = checker.package_crossings()
    (crossing,) = crossings.crossings
    renames = ModuleRenames({"low.before_the_move": crossing.importing_module})
    base = PackageCrossings(
        crossings=(
            BoundaryCrossing(
                importing_module="low.before_the_move",
                imported_module=crossing.imported_module,
            ),
        )
    )

    assert crossings.added_since(base.renamed(renames)) == ()


@pytest.fixture
def moved_package(scratch_repository) -> tuple[PackageBoundaryChecker, str]:
    """
    :return: A checker of the dataset's workspace committed in a scratch repository,
        and the commit before its lower distribution's importing module was moved.
    """
    workspace = scratch_repository.project_root / PackageBoundarySnippet.DIRECTORY.name
    shutil.copytree(PackageBoundarySnippet.DIRECTORY.value, workspace)
    scratch_repository.commit_everything("add the workspace")
    base_commit = scratch_repository.git.commit_at("HEAD")
    low = workspace / PackageBoundarySnippet.UNLISTED_IMPORT.relative_to(
        PackageBoundarySnippet.DIRECTORY
    )
    scratch_repository.run_git("mv", str(low), str(low.with_name("moved.py")))
    scratch_repository.commit_everything("move the importing module")
    return PackageBoundaryChecker(Workspace(workspace)), base_commit


def test_a_module_git_detects_as_moved_is_renamed(moved_package, scratch_repository):
    """
    The importing module's move is read as a rename from its old dotted name.
    """
    checker, base_commit = moved_package

    assert checker.module_renames(scratch_repository.git, base_commit) == (
        ModuleRenames({"low.upward": "low.moved"})
    )


# %% the package at another commit


def test_the_package_at_a_commit_is_read_under_that_commit_s_distributions(
    moved_package, scratch_repository, checker
):
    """
    The base commit's package holds the crossings under the names it had then.
    """
    moved_checker, base_commit = moved_package

    with PackageAtCommit(
        scratch_repository.git, base_commit, moved_checker.workspace.root
    ) as base_checker:
        base_crossings = base_checker.package_crossings()

    assert base_crossings == checker.package_crossings()


def test_the_package_at_a_commit_is_removed_on_exit(moved_package, scratch_repository):
    """
    Reading the base leaves no worktree behind.
    """
    moved_checker, base_commit = moved_package
    package_at_commit = PackageAtCommit(
        scratch_repository.git, base_commit, moved_checker.workspace.root
    )

    with package_at_commit:
        pass

    assert not package_at_commit.directory.exists()


def test_a_commit_holding_no_distributions_has_no_checker(scratch_repository):
    """
    A commit from before the distributions moved into a workspace has nothing to
    compare.
    """
    shutil.copy(PackageBoundarySnippet.UNLISTED_IMPORT, scratch_repository.project_root)
    scratch_repository.commit_everything("a module outside any workspace")

    with PackageAtCommit(
        scratch_repository.git, "HEAD", scratch_repository.project_root
    ) as base_checker:
        assert base_checker is None
