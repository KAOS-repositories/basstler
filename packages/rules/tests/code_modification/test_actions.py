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
from basstler.text_file import TextFile

from basstler_testing.constants.paths import CodeModificationSnippet

# %% the module changed


@pytest.fixture
def two_calls() -> PositionedModule:
    """
    :return: The module calling :func:`abs` and then :func:`round`.
    """
    return PositionedModule(
        libcst.parse_module(TextFile(CodeModificationSnippet.TWO_CALLS).read())
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

    assert (
        applied.result.code
        == TextFile(CodeModificationSnippet.TWO_CALLS_FIRST_RENAMED).read()
    )


def test_the_inverse_of_a_replacement_restores_the_module_exactly(two_calls):
    """
    Undoing a replacement gives back the source it was applied to, character for
    character.
    """
    applied = first_call_replacement(two_calls, "float").apply(two_calls.module)

    assert applied.inverse.apply(applied.result).result.code == two_calls.module.code


def test_a_replacement_whose_node_is_gone_raises(two_calls):
    """
    A replacement applied a second time no longer finds the node it replaces.
    """
    replacement = first_call_replacement(two_calls, "float")
    applied = replacement.apply(two_calls.module)

    with pytest.raises(ActionTargetMissingError):
        replacement.apply(applied.result)


# %% plans


def test_a_plan_is_undone_in_the_reverse_order_it_was_applied(two_calls):
    """
    A plan whose second action changes what the first one put in place is undone
    exactly, the second action first.
    """
    first = first_call_replacement(two_calls, "float")
    renamed = PositionedModule(first.apply(two_calls.module).result)
    plan = ActionPlan((first, first_call_replacement(renamed, "int")))

    applied = plan.apply(two_calls.module)

    assert applied.inverse.apply(applied.result).result.code == two_calls.module.code


# %% inserting an import


@pytest.fixture
def imports() -> libcst.Module:
    """
    :return: The module that imports :mod:`os`.
    """
    return libcst.parse_module(TextFile(CodeModificationSnippet.IMPORTS).read())


def test_an_import_follows_the_last_import_of_the_module(imports):
    """
    The statement is inserted right after the module's last import.
    """
    applied = ImportInsertion(TextFile).apply(imports)

    assert applied.result.code == (
        TextFile(CodeModificationSnippet.IMPORTS_WITH_TEXT_FILE).read()
    )


def test_an_import_joins_the_import_of_its_module():
    """
    A class of a module the module imports from is added to that import.
    """
    module = libcst.parse_module(
        TextFile(CodeModificationSnippet.IMPORTS_OF_TEXT_FILE_MODULE).read()
    )

    assert ImportInsertion(TextFile).apply(module).result.code == (
        TextFile(CodeModificationSnippet.IMPORTS_OF_TEXT_FILE_MODULE_MERGED).read()
    )


def test_an_import_the_module_already_has_is_not_inserted_again(imports):
    """
    Inserting an import twice changes the module once.
    """
    once = ImportInsertion(TextFile).apply(imports).result

    assert ImportInsertion(TextFile).apply(once).result.code == once.code


def test_the_inverse_of_an_import_restores_the_module_exactly(imports):
    """
    Undoing the insertion gives back the source it was applied to.
    """
    applied = ImportInsertion(TextFile).apply(imports)

    assert applied.inverse.apply(applied.result).result.code == imports.code


def test_the_inverse_of_an_import_already_there_changes_nothing(imports):
    """
    An insertion that changed nothing is undone by changing nothing.
    """
    once = ImportInsertion(TextFile).apply(imports).result
    applied = ImportInsertion(TextFile).apply(once)

    assert applied.inverse.apply(applied.result).result.code == once.code
