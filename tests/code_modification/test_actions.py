"""
Tests for :mod:`basstler.code_modification.actions`: replacing nodes, plans of actions,
and undoing both exactly.
"""

from __future__ import annotations

import libcst
import pytest

from basstler.code_modification.actions import (
    ActionPlan,
    ImportInsertion,
    NodeReplacement,
)
from basstler.code_modification.exceptions import ActionTargetMissingError
from basstler.code_modification.positions import PositionedModule

from ..constants.paths import CodeModificationSnippet

# %% the module changed


@pytest.fixture
def two_calls() -> PositionedModule:
    """
    :return: The module calling :func:`abs` and then :func:`round`.
    """
    return PositionedModule(
        libcst.parse_module(
            CodeModificationSnippet.TWO_CALLS.read_text(encoding="utf-8")
        )
    )


def first_call_replacement(module: PositionedModule, name: str) -> NodeReplacement:
    """
    :param module: A module whose first call is to be renamed.
    :param name: The name the call's function gets.
    :return: The replacement of that call by a call of *name* with its arguments.
    """
    call, location = next(
        (node, location)
        for node, location in module.positions.items()
        if isinstance(node, libcst.Call)
    )
    return NodeReplacement(location, call, call.with_changes(func=libcst.Name(name)))


# %% replacing a node


def test_a_replacement_changes_only_its_node(two_calls):
    """
    Replacing the first call leaves the docstring and the second call as they are.
    """
    applied = first_call_replacement(two_calls, "float").apply(two_calls.module)

    assert applied.module.code == (
        CodeModificationSnippet.TWO_CALLS_FIRST_RENAMED.read_text(encoding="utf-8")
    )


def test_the_inverse_of_a_replacement_restores_the_module_exactly(two_calls):
    """
    Undoing a replacement gives back the source it was applied to, character for
    character.
    """
    applied = first_call_replacement(two_calls, "float").apply(two_calls.module)

    assert applied.inverse.apply(applied.module).module.code == two_calls.module.code


def test_a_replacement_whose_node_is_gone_raises(two_calls):
    """
    A replacement applied a second time no longer finds the node it replaces.
    """
    replacement = first_call_replacement(two_calls, "float")
    applied = replacement.apply(two_calls.module)

    with pytest.raises(ActionTargetMissingError):
        replacement.apply(applied.module)


# %% plans


def test_a_plan_is_undone_in_the_reverse_order_it_was_applied(two_calls):
    """
    A plan whose second action changes what the first one put in place is undone
    exactly, the second action first.
    """
    first = first_call_replacement(two_calls, "float")
    renamed = PositionedModule(first.apply(two_calls.module).module)
    plan = ActionPlan((first, first_call_replacement(renamed, "int")))

    applied = plan.apply(two_calls.module)

    assert applied.inverse.apply(applied.module).module.code == two_calls.module.code


# %% inserting an import


@pytest.fixture
def text_file_import() -> libcst.SimpleStatementLine:
    """
    :return: The statement importing :class:`~basstler.text_file.TextFile`.
    """
    return libcst.parse_statement("from basstler.text_file import TextFile\n")


@pytest.fixture
def imports() -> libcst.Module:
    """
    :return: The module that imports :mod:`os`.
    """
    return libcst.parse_module(
        CodeModificationSnippet.IMPORTS.read_text(encoding="utf-8")
    )


def test_an_import_follows_the_last_import_of_the_module(imports, text_file_import):
    """
    The statement is inserted right after the module's last import.
    """
    applied = ImportInsertion(text_file_import).apply(imports)

    assert applied.module.code == (
        CodeModificationSnippet.IMPORTS_WITH_TEXT_FILE.read_text(encoding="utf-8")
    )


def test_an_import_the_module_already_has_is_not_inserted_again(
    imports, text_file_import
):
    """
    Inserting an import twice changes the module once.
    """
    once = ImportInsertion(text_file_import).apply(imports).module

    assert ImportInsertion(text_file_import).apply(once).module.code == once.code


def test_the_inverse_of_an_import_restores_the_module_exactly(
    imports, text_file_import
):
    """
    Undoing the insertion gives back the source it was applied to.
    """
    applied = ImportInsertion(text_file_import).apply(imports)

    assert applied.inverse.apply(applied.module).module.code == imports.code


def test_the_inverse_of_an_import_already_there_changes_nothing(
    imports, text_file_import
):
    """
    An insertion that changed nothing is undone by changing nothing.
    """
    once = ImportInsertion(text_file_import).apply(imports).module
    applied = ImportInsertion(text_file_import).apply(once)

    assert applied.inverse.apply(applied.module).module.code == once.code
