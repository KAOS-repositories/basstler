"""
Tests for :mod:`basstler.code_modification.actions`: replacing nodes, plans of actions,
and undoing both exactly.
"""

from __future__ import annotations

from concurrent.futures import Future

import libcst
import pytest

from basstler.code_modification.actions import (
    ActionPlan,
    ImportInsertion,
    NodeReplacement,
    NodeReplacements,
)
from basstler.code_modification.exceptions import ActionTargetMissingError
from basstler.code_modification.positions import PositionedModule
from basstler.text_file import TextFile

from ..constants.paths import CodeModificationSnippet

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
        applied.module.code
        == TextFile(CodeModificationSnippet.TWO_CALLS_FIRST_RENAMED).read()
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


# %% replacing several nodes at once


def call_replacements(
    module: PositionedModule, names: tuple[str, ...]
) -> NodeReplacements:
    """
    :param module: A module whose calls are to be renamed.
    :param names: The name each call's function gets, in the order of the calls.
    :return: The replacements of those calls by calls of *names* with their arguments.
    """
    calls = [
        (node, location)
        for node, location in module.positions.items()
        if isinstance(node, libcst.Call)
    ]
    return NodeReplacements(
        tuple(
            NodeReplacement(location, call, call.with_changes(func=libcst.Name(name)))
            for (call, location), name in zip(calls, names, strict=True)
        )
    )


def test_replacements_made_at_once_change_each_of_their_nodes(two_calls):
    """
    Both calls are replaced, and nothing else changes.
    """
    applied = call_replacements(two_calls, ("float", "int")).apply(two_calls.module)

    assert (
        applied.module.code
        == TextFile(CodeModificationSnippet.TWO_CALLS_BOTH_RENAMED).read()
    )


def test_the_inverse_of_replacements_made_at_once_restores_the_module_exactly(
    two_calls,
):
    """
    Undoing the replacements gives back the source they were applied to.
    """
    applied = call_replacements(two_calls, ("float", "int")).apply(two_calls.module)

    assert applied.inverse.apply(applied.module).module.code == two_calls.module.code


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

    assert applied.module.code == (
        TextFile(CodeModificationSnippet.IMPORTS_WITH_TEXT_FILE).read()
    )


def test_a_class_defined_in_a_private_module_is_imported_from_its_public_one(imports):
    """
    A class is imported from the module that exports it, never from the private module
    it is defined in.
    """
    applied = ImportInsertion(Future).apply(imports)

    assert applied.module.code == (
        TextFile(CodeModificationSnippet.IMPORTS_WITH_FUTURE).read()
    )


def test_an_import_joins_the_import_of_its_module():
    """
    A class of a module the module imports from is added to that import.
    """
    module = libcst.parse_module(
        TextFile(CodeModificationSnippet.IMPORTS_OF_TEXT_FILE_MODULE).read()
    )

    assert ImportInsertion(TextFile).apply(module).module.code == (
        TextFile(CodeModificationSnippet.IMPORTS_OF_TEXT_FILE_MODULE_MERGED).read()
    )


def test_an_import_the_module_already_has_is_not_inserted_again(imports):
    """
    Inserting an import twice changes the module once.
    """
    once = ImportInsertion(TextFile).apply(imports).module

    assert ImportInsertion(TextFile).apply(once).module.code == once.code


def test_the_inverse_of_an_import_restores_the_module_exactly(imports):
    """
    Undoing the insertion gives back the source it was applied to.
    """
    applied = ImportInsertion(TextFile).apply(imports)

    assert applied.inverse.apply(applied.module).module.code == imports.code


def test_the_inverse_of_an_import_already_there_changes_nothing(imports):
    """
    An insertion that changed nothing is undone by changing nothing.
    """
    once = ImportInsertion(TextFile).apply(imports).module
    applied = ImportInsertion(TextFile).apply(once)

    assert applied.inverse.apply(applied.module).module.code == once.code
