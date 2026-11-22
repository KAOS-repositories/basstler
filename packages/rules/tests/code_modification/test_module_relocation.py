"""
Tests for :mod:`basstler.code_modification.module_relocation`: moving modules within a
source tree, rewriting the imports the move breaks, and undoing it exactly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.code_modification.exceptions import UnrewritableImportError
from basstler.code_modification.file_actions import FileMove
from basstler.code_modification.module_relocation import ImportRoots, ModuleRelocation
from basstler.code_modification.source_tree import SourceTree

from basstler_testing.constants.paths import RelocationTree

# %% the trees moved in


@pytest.fixture
def before() -> SourceTree:
    """
    :return: The package whose tests import its helper and a sibling.
    """
    return SourceTree.of_directory(RelocationTree.BEFORE)


TREE_ROOT = ImportRoots((Path(),))
"""
The tree's own root as the one directory modules are imported from.
"""

HELPER_MOVE = ModuleRelocation(
    (FileMove(Path("project/helper.py"), Path("support/shared/helper.py")),),
    TREE_ROOT,
)
"""
The relocation of the package's helper to ``support/shared``.
"""

TESTS_MOVE = ModuleRelocation(
    tuple(
        FileMove(Path("project/tests") / name, Path("elsewhere/tests") / name)
        for name in ("__init__.py", "helper_user.py", "sibling.py")
    ),
    TREE_ROOT,
)
"""
The relocation of every module of the package's tests to ``elsewhere/tests``.
"""


# %% moving modules


def test_an_import_of_a_moved_module_names_it_where_it_is_now(before):
    """
    The relative import of the helper no longer resolves once the helper moves, so it
    imports the helper by its new name; nothing else changes.
    """
    assert HELPER_MOVE.apply(before).result == SourceTree.of_directory(
        RelocationTree.HELPER_MOVED
    )


def test_modules_moved_together_keep_their_relative_imports(before):
    """
    The import of the sibling moved along stays relative; the import of the helper left
    behind names it absolutely.
    """
    assert TESTS_MOVE.apply(before).result == SourceTree.of_directory(
        RelocationTree.TESTS_MOVED
    )


@pytest.mark.parametrize("relocation", [HELPER_MOVE, TESTS_MOVE])
def test_the_inverse_of_a_relocation_restores_the_tree_exactly(before, relocation):
    """
    Undoing a relocation moves every file back and restores every import it rewrote,
    byte for byte.
    """
    applied = relocation.apply(before)

    assert applied.inverse.apply(applied.result).result == before


def test_a_dotted_import_of_a_moved_module_is_refused():
    """
    ``import project.helper`` binds the name ``project``, which no rewrite of the
    statement alone keeps, so the relocation refuses to make it.
    """
    tree = SourceTree.of_directory(RelocationTree.DOTTED_IMPORT)

    with pytest.raises(UnrewritableImportError):
        HELPER_MOVE.apply(tree)
