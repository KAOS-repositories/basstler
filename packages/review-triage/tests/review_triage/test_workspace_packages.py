"""
Tests for :mod:`basstler.review_triage.workspace_packages`: the plan splitting one
package into a directory per distribution, built from the base tree alone.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.code_modification.source_tree import SourceTree
from basstler.review_triage.workspace_packages import WorkspacePackagesPlan

from .samples import WorkspacePackagesSample

BASE = SourceTree.of_directory(WorkspacePackagesSample.BASE_TREE.path)
"""
The sample's single package, before the plan.
"""

HEAD = SourceTree.of_directory(WorkspacePackagesSample.HEAD_TREE.path)
"""
The sample split into a directory per distribution, as the plan has to leave it.
"""


@pytest.fixture(scope="module")
def replayed() -> SourceTree:
    """
    :return: The sample's base tree once the plan built from it is applied.
    """
    return WorkspacePackagesPlan().build(BASE).apply(BASE).result


# %% where each file goes


@pytest.mark.parametrize("path", sorted(HEAD.files), ids=str)
def test_each_file_of_the_split_tree_is_where_the_plan_puts_it(
    replayed: SourceTree, path: Path
):
    """
    Every module, template, test and helper lands where its distribution or the shared
    test support keeps it, its broken imports rewritten.
    """
    assert replayed.files.get(path) == HEAD.files[path]


def test_the_plan_leaves_no_other_file(replayed: SourceTree):
    """
    Nothing stays at its old path, and the package's own initializer is gone.
    """
    assert sorted(replayed.files) == sorted(HEAD.files)


def test_undoing_the_plan_restores_the_base_exactly():
    """
    The plan's inverse turns the split tree back into the single package.
    """
    applied = WorkspacePackagesPlan().build(BASE).apply(BASE)

    assert applied.inverse.apply(applied.result).result == BASE
