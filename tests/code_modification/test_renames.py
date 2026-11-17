"""
Tests for :mod:`basstler.code_modification.renames`: renaming a symbol in a module
wherever it is named, leaving text that only mentions it, and undoing it exactly.
"""

from __future__ import annotations

import libcst
import pytest

from basstler.code_modification.actions import ActionPlan
from basstler.code_modification.command_line import (
    CodeModificationExitCode,
    rename as rename_symbol,
)
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.renames import SymbolRename

from ..constants.paths import CodeModificationSnippet

# %% the module renamed

OLD_NAME = "Serializer"
"""
The class the snippets name.
"""

NEW_NAME = "PythonSerializer"
"""
What the class is renamed to.
"""


@pytest.fixture
def before() -> libcst.Module:
    """
    :return: The module naming :data:`OLD_NAME` in every kind of place.
    """
    return libcst.parse_module(
        CodeModificationSnippet.RENAMED_SYMBOL_BEFORE.read_text(encoding="utf-8")
    )


@pytest.fixture
def rename() -> SymbolRename:
    """
    :return: The rename of :data:`OLD_NAME` to :data:`NEW_NAME`.
    """
    return SymbolRename(old_name=OLD_NAME, new_name=NEW_NAME)


# %% renaming


def test_every_place_naming_the_symbol_is_renamed_and_nothing_else(before, rename):
    """
    Imports, a base class, annotations, calls and an attribute are renamed; the
    docstring, the comment and the string, which only mention the name, are not.
    """
    applied = rename.apply(before)

    assert applied.module.code == (
        CodeModificationSnippet.RENAMED_SYMBOL_AFTER.read_text(encoding="utf-8")
    )


def test_an_import_alias_keeps_the_name_it_binds(before, rename):
    """
    ``import Serializer as Writer`` imports the renamed class under the same alias.
    """
    applied = rename.apply(before)

    assert "import PythonSerializer as Writer" in applied.module.code
    assert "import Serializer as Writer" not in applied.module.code


def test_the_inverse_restores_the_module_exactly(before, rename):
    """
    Applying the inverse of a rename gives back the source character for character.
    """
    applied = rename.apply(before)

    assert applied.inverse.apply(applied.module).module.code == before.code


def test_the_occurrences_are_the_places_the_name_is_a_name(before, rename):
    """
    Each occurrence holds the name it replaces, at the place the module has it.
    """
    positioned = PositionedModule(before)

    occurrences = rename.occurrences(module=positioned)

    assert [occurrence.node.value for occurrence in occurrences] == [OLD_NAME] * 5
    assert [occurrence.location.start.line for occurrence in occurrences] == [
        8,
        9,
        12,
        17,
        22,
    ]


def test_a_module_without_the_symbol_is_left_as_it_is(rename):
    """
    There is nothing to rename, so the plan is empty and the source is unchanged.
    """
    module = libcst.parse_module("value = 1\n")

    applied = rename.apply(module)

    assert applied.module.code == module.code
    assert applied.inverse == ActionPlan()


# %% the command


def test_the_command_renames_each_file_and_reports_the_change(tmp_path):
    """
    A file naming the symbol is rewritten as the rename gives it, and the exit status
    says something changed.
    """
    source = tmp_path / "module.py"
    source.write_text(
        CodeModificationSnippet.RENAMED_SYMBOL_BEFORE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    status = rename_symbol(OLD_NAME, NEW_NAME, [source])

    assert status == CodeModificationExitCode.CHANGES_MADE
    assert source.read_text(encoding="utf-8") == (
        CodeModificationSnippet.RENAMED_SYMBOL_AFTER.read_text(encoding="utf-8")
    )


def test_the_command_leaves_a_file_without_the_symbol_alone(tmp_path):
    """
    Nothing is written for a file that does not name the symbol.
    """
    source = tmp_path / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")

    status = rename_symbol(OLD_NAME, NEW_NAME, [source])

    assert status == CodeModificationExitCode.SUCCESS
    assert source.read_text(encoding="utf-8") == "value = 1\n"
