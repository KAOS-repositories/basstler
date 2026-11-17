"""
Tests for :mod:`basstler.code_modification.relocations`: importing a name from the module
it moved to, and undoing it exactly.
"""

from __future__ import annotations

import libcst
import pytest

from basstler.code_modification.command_line import (
    CodeModificationExitCode,
    relocate_import,
)
from basstler.code_modification.exceptions import ImportRelocationUnsupportedError
from basstler.code_modification.relocations import ImportRelocation

from ..constants.paths import CodeModificationSnippet

# %% the module changed


@pytest.fixture
def before() -> libcst.Module:
    """
    :return: The module importing :data:`NAME` from :data:`OLD_MODULE` twice.
    """
    return libcst.parse_module(
        CodeModificationSnippet.RELOCATED_IMPORT_BEFORE.read_text(encoding="utf-8")
    )


@pytest.fixture
def relocation() -> ImportRelocation:
    """
    :return: The relocation of ``Mover`` from ``helpers`` to ``relocated``.
    """
    return ImportRelocation(name="Mover", old_module="helpers", new_module="relocated")


# %% relocating


def test_every_import_of_the_name_from_the_old_module_moves(before, relocation):
    """
    Both imports of the name, one aliased, come from the new module; the import of
    another name from the old module, and of the same name from another module, stay.
    """
    applied = relocation.apply(before)

    assert applied.module.code == (
        CodeModificationSnippet.RELOCATED_IMPORT_AFTER.read_text(encoding="utf-8")
    )


def test_the_inverse_restores_the_module_exactly(before, relocation):
    """
    Applying the inverse gives back the source character for character.
    """
    applied = relocation.apply(before)

    assert applied.inverse.apply(applied.module).module.code == before.code


def test_an_import_of_other_names_beside_the_moved_one_is_refused(relocation):
    """
    One statement cannot import from two modules, so the relocation names the line it
    cannot move instead of dropping the other names.
    """
    module = libcst.parse_module("from helpers import Mover, Other\n")

    with pytest.raises(ImportRelocationUnsupportedError):
        relocation.apply(module)


# %% the command


def test_the_command_relocates_each_file_and_reports_the_change(tmp_path):
    """
    A file importing the name from the old module is rewritten, and the exit status
    says something changed.
    """
    source = tmp_path / "module.py"
    source.write_text(
        CodeModificationSnippet.RELOCATED_IMPORT_BEFORE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    status = relocate_import("Mover", "helpers", "relocated", [source])

    assert status == CodeModificationExitCode.CHANGES_MADE
    assert source.read_text(encoding="utf-8") == (
        CodeModificationSnippet.RELOCATED_IMPORT_AFTER.read_text(encoding="utf-8")
    )
