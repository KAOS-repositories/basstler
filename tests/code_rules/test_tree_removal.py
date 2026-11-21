"""
Tests for :mod:`basstler.code_rules.tree_removal`: reporting directories removed with
:func:`shutil.rmtree`, which stops at the read-only object files git leaves on Windows.
"""

from __future__ import annotations

from pathlib import Path

from basstler import directory_tree
from basstler.code_rules.checker import CodeRulesCheck
from basstler.code_rules.tree_removal import TreeRemovalChecker

from ..constants.paths import TreeRemovalSnippet
from .marked_snippet import MarkedSnippet

# %% removals


def test_every_shutil_rmtree_is_reported():
    """
    Each call is reported, whether or not it ignores errors.
    """
    snippet = MarkedSnippet(TreeRemovalSnippet.SHUTIL_RMTREE)
    assert snippet.reported_lines(TreeRemovalChecker()) == snippet.marked_lines


def test_a_rmtree_imported_under_another_name_is_reported():
    """
    The module is resolved through its imports, not matched by its spelling.
    """
    snippet = MarkedSnippet(TreeRemovalSnippet.IMPORTED_RMTREE)
    assert snippet.reported_lines(TreeRemovalChecker()) == snippet.marked_lines


def test_a_function_named_rmtree_that_is_not_the_shutil_one_is_not_reported():
    """
    A function or method sharing the name is not :func:`shutil.rmtree`.
    """
    snippet = MarkedSnippet(TreeRemovalSnippet.OTHER_RMTREE)
    assert snippet.reported_lines(TreeRemovalChecker()) == snippet.marked_lines


def test_the_module_removing_trees_is_not_reported():
    """
    The one module allowed to call :func:`shutil.rmtree` is left out.
    """
    assert list(TreeRemovalChecker().violations(Path(directory_tree.__file__))) == []


# %% this repository


def test_no_code_in_the_repository_removes_a_directory_with_shutil_rmtree(
    repository_sources,
):
    """
    Every directory the package, its scripts and its suite remove goes through
    :class:`basstler.directory_tree.DirectoryTree`, so the suite passes on Windows too.
    """
    violations = CodeRulesCheck((TreeRemovalChecker(),)).violations(repository_sources)
    assert [violation.render() for violation in violations] == []
