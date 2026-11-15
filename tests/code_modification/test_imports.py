"""
Tests for :mod:`basstler.code_modification.imports`: adding the import a fix needs, and
undoing it exactly.
"""

from __future__ import annotations

import libcst
import pytest

from basstler.bash import Bash
from basstler.code_modification.imports import ImportedName
from basstler.directory_tree import DirectoryTree

from ..constants.paths import CodeModificationSnippet

# %% the import added

DIRECTORY_TREE_IMPORT = ImportedName(DirectoryTree.__module__, DirectoryTree.__name__)
"""
The import of :class:`basstler.directory_tree.DirectoryTree`.
"""


def module_of(snippet: CodeModificationSnippet) -> libcst.Module:
    """
    :return: The module in *snippet*.
    """
    return libcst.parse_module(snippet.read_text(encoding="utf-8"))


def test_an_import_is_added_after_the_last_import():
    """
    The new import follows the imports already there, before the code.
    """
    module = module_of(CodeModificationSnippet.IMPORTS_BEFORE_CODE)

    added = DIRECTORY_TREE_IMPORT.addition_to(module).apply(module).module

    assert added.code == module.code.replace(
        "from pathlib import Path\n",
        "from pathlib import Path\n"
        f"from {DirectoryTree.__module__} import {DirectoryTree.__name__}\n",
    )


def test_an_import_is_added_after_the_docstring_of_a_module_importing_nothing():
    """
    A module with no import gets the import right below its docstring.
    """
    module = module_of(CodeModificationSnippet.NO_IMPORTS)

    added = DIRECTORY_TREE_IMPORT.addition_to(module).apply(module).module

    assert added.code == module.code.replace(
        '"""\n\nprint',
        '"""\n'
        f"from {DirectoryTree.__module__} import {DirectoryTree.__name__}\n\nprint",
    )


def test_a_name_imported_among_others_is_not_imported_again():
    """
    Nothing changes where the name is already imported, as one of several.
    """
    module = module_of(CodeModificationSnippet.IMPORTS_WITH_BASH)

    applied = (
        ImportedName(Bash.__module__, Bash.__name__).addition_to(module).apply(module)
    )

    assert applied.module.code == module.code


@pytest.mark.parametrize(
    "snippet",
    [
        CodeModificationSnippet.IMPORTS_BEFORE_CODE,
        CodeModificationSnippet.NO_IMPORTS,
    ],
    ids=lambda snippet: snippet.name,
)
def test_undoing_an_added_import_restores_the_module_exactly(snippet):
    """
    The inverse of adding the import is the module as it was, character for character.
    """
    module = module_of(snippet)

    applied = DIRECTORY_TREE_IMPORT.addition_to(module).apply(module)

    assert applied.inverse.apply(applied.module).module.code == module.code
