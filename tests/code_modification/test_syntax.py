"""
Tests for :mod:`basstler.code_modification.syntax`: what an expression or a call says,
read from its syntax tree, and calls passed one more argument.
"""

from __future__ import annotations

from pathlib import Path
from typing import override

import libcst

from basstler.code_modification.source_file import PythonSourceFile
from basstler.code_modification.syntax import (
    BodySyntax,
    CallSyntax,
    ConstantName,
    ExpressionSyntax,
)

from basstler.text_file import TextFile

from ..constants.paths import CodeModificationSnippet

# %% names


def test_the_final_name_is_what_an_expression_refers_to_last():
    """
    A name, an attribute and a subscript each refer to a name; a call's result does not.
    """
    module = PythonSourceFile(CodeModificationSnippet.CALLED_NAMES).parse()
    calls = [
        node.value
        for statement in module.body
        if isinstance(statement, libcst.SimpleStatementLine)
        for node in statement.body
        if isinstance(node, libcst.Expr) and isinstance(node.value, libcst.Call)
    ]

    assert [ExpressionSyntax(call.func).final_name for call in calls] == [
        open.__name__,
        Path.read_text.__name__,
        dict.__name__,
        None,
    ]


# %% constants


def test_literals_and_constant_names_are_constants():
    """
    Literals and the names bound to constants are constants; a variable and a formatted
    string are not.
    """
    module = PythonSourceFile(CodeModificationSnippet.EXPRESSIONS).parse()
    statement = libcst.ensure_type(module.body[-1], libcst.SimpleStatementLine)
    expression = libcst.ensure_type(statement.body[0], libcst.Expr)
    elements = libcst.ensure_type(expression.value, libcst.Tuple).elements

    assert [ExpressionSyntax(element.value).is_constant for element in elements] == [
        True,
        True,
        True,
        True,
        True,
        False,
        False,
    ]


# %% passing one more argument


class CheckPassing(libcst.CSTTransformer):
    """
    Passes ``check=True`` to every call.
    """

    @override
    def leave_Call(
        self, original_node: libcst.Call, updated_node: libcst.Call
    ) -> libcst.Call:
        """
        :return: *updated_node* passing ``check=True`` last.
        """
        return CallSyntax(updated_node).with_argument_appended(
            CallSyntax.keyword_argument("check", libcst.Name(ConstantName.TRUE))
        )


def test_an_appended_argument_follows_the_layout_of_the_call():
    """
    An argument is appended after the others, on a line of its own where the call puts
    each argument on one, keeping a trailing comma last.
    """
    module = PythonSourceFile(CodeModificationSnippet.CALL_ARGUMENTS).parse()

    passed = module.visit(CheckPassing())

    assert (
        passed.code
        == PythonSourceFile(CodeModificationSnippet.CALL_ARGUMENTS_WITH_CHECK).read()
    )


# %% bodies


def test_a_body_lists_the_statements_sharing_a_line_one_by_one():
    """
    Each statement of a simple line is a statement of its own; a compound one is whole.
    """
    body = BodySyntax(
        libcst.parse_module(TextFile(CodeModificationSnippet.BODY).read())
    )

    assert [type(statement) for statement in body.statements] == [
        libcst.Expr,
        libcst.ImportFrom,
        libcst.Assign,
        libcst.Expr,
        libcst.Expr,
        libcst.Expr,
        libcst.If,
    ]


def test_only_a_string_literal_statement_is_a_string():
    """
    The docstring and the strings are strings; a call is not.
    """
    body = BodySyntax(
        libcst.parse_module(TextFile(CodeModificationSnippet.BODY).read())
    )

    assert [BodySyntax.is_string(statement) for statement in body.statements] == [
        True,
        False,
        False,
        True,
        True,
        False,
        False,
    ]
