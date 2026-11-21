"""
Tests for :mod:`basstler.code_rules.tree_removal`: reporting directories removed with
:func:`shutil.rmtree`, which stops at the read-only object files git leaves on Windows.
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path


from basstler import directory_tree
from basstler.code_modification.source_file import PythonSourceFile
from basstler.code_rules.commands import CodeRulesCommand
from basstler.code_rules.checker import CodeRulesCheck
from basstler.code_rules.fixes import SourceFixer
from basstler.code_rules.tree_removal import RemovalKeyword, TreeRemovalChecker
from basstler.directory_tree import DirectoryTree

from ..constants.paths import TreeRemovalSnippet

# %% removals


def test_every_shutil_rmtree_is_reported():
    """
    Each call is reported, whether or not it ignores errors.
    """
    violations = TreeRemovalChecker().violations(TreeRemovalSnippet.SHUTIL_RMTREE)
    assert [violation.first_line for violation in violations] == [10, 11]


def test_the_module_removing_trees_is_not_reported():
    """
    The one module allowed to call :func:`shutil.rmtree` is left out.
    """
    assert list(TreeRemovalChecker().violations(Path(directory_tree.__file__))) == []


# %% what the fix leaves


def test_a_call_with_an_error_handler_is_reported_without_a_fix():
    """
    A call passing what :class:`DirectoryTree` cannot take over is reported, and the
    report does not promise the fix.
    """
    violations = list(
        TreeRemovalChecker().violations(TreeRemovalSnippet.HANDLED_RMTREE)
    )
    assert [violation.first_line for violation in violations] == [17]
    assert violations[0].description.endswith(
        f"`{CodeRulesCommand.FIX.invocation}` leaves it"
    )


def test_the_fix_leaves_a_call_with_an_error_handler_as_it_is():
    """
    Fixing changes nothing in a module whose only removal has a handler.
    """
    source_file = PythonSourceFile(TreeRemovalSnippet.HANDLED_RMTREE)
    fixed = SourceFixer((TreeRemovalChecker(),)).fix_module(
        source_file.parse(), source_file.path
    )
    assert fixed.module.code == source_file.read()


def test_the_keyword_the_fix_keeps_is_a_field_of_the_tree():
    """
    The keyword :func:`shutil.rmtree` has that the tree takes over is a field of it.
    """
    assert RemovalKeyword.IGNORE_ERRORS in {
        field.name for field in fields(DirectoryTree)
    }


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
