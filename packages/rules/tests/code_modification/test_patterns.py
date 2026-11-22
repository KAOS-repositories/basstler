"""
Tests for :mod:`basstler.code_modification.patterns`: finding the nodes of a module that
have the shape a pattern declares.
"""

from __future__ import annotations

import libcst
import pytest
from libcst import matchers

from basstler.class_property import classproperty
from basstler.code_modification.patterns import CodePattern
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.source_file import EditablePythonSourceFile

from basstler_testing.constants.paths import CodeModificationSnippet

# %% a pattern

FIRST_ARGUMENT_SAVED_AS = "first"


class RunCallWithArgument(CodePattern):
    """
    A call of ``run`` given at least one argument, the first of which is saved.
    """

    @classproperty
    def matcher(cls) -> matchers.Call:
        return matchers.Call(
            func=matchers.Name("run"),
            args=[
                matchers.SaveMatchedNode(matchers.Arg(), FIRST_ARGUMENT_SAVED_AS),
                matchers.ZeroOrMore(),
            ],
        )


def module() -> PositionedModule:
    """
    :return: The module of calls without arguments, with one, and with a trailing comma.
    """
    return PositionedModule(
        EditablePythonSourceFile(CodeModificationSnippet.CALL_ARGUMENTS).parse()
    )


# %% finding


def source_of(node: libcst.CSTNode) -> str:
    """
    :return: The source text of *node*.
    """
    return libcst.Module([]).code_for_node(node)


def test_the_nodes_with_the_shape_are_found_in_the_order_of_the_source():
    """
    Of the three calls of ``run``, the one given nothing is not found.
    """
    occurrences = list(RunCallWithArgument.found_in(module()))

    assert [source_of(occurrence.node) for occurrence in occurrences] == [
        "run(command)",
        "run(\n    command,\n)",
    ]


def test_an_occurrence_is_the_node_and_its_code_range():
    """
    The code range is the one the module records for the node.
    """
    positioned = module()

    for occurrence in RunCallWithArgument.found_in(positioned):
        assert occurrence.location == positioned.positions[occurrence.node]


# %% matching


@pytest.mark.parametrize(
    ("source", "has_the_shape"),
    [
        ("run(command)", True),
        ("run(command, check)", True),
        ("run()", False),
        ("walk(command)", False),
        ("run", False),
    ],
)
def test_a_node_matches_only_the_pattern_it_has_the_shape_of(
    source: str, has_the_shape: bool
):
    """
    A call of ``run`` given an argument matches; a call given none, and a name, do not.
    """
    assert RunCallWithArgument.matches(libcst.parse_expression(source)) is has_the_shape


# %% capturing


def test_the_nodes_the_matcher_saves_are_captured_by_name():
    """
    The first argument is captured; a node of another shape captures nothing.
    """
    call = libcst.ensure_type(
        libcst.parse_expression("run(command, check)"), libcst.Call
    )

    assert RunCallWithArgument.captures(call) == {FIRST_ARGUMENT_SAVED_AS: call.args[0]}
    assert RunCallWithArgument.captures(libcst.Name("run")) is None
