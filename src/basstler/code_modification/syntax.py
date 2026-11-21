"""
What an expression or a call says, read from its concrete syntax tree without running
it, and calls changed to pass other arguments.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property

import libcst

# %% names


class ConstantName(StrEnum):
    """
    The names Python binds to constants rather than to variables.
    """

    TRUE = str(True)
    """
    The name of :data:`True`.
    """

    FALSE = str(False)
    """
    The name of :data:`False`.
    """

    NONE = str(None)
    """
    The name of :data:`None`.
    """


# %% expressions


@dataclass(frozen=True)
class ExpressionSyntax:
    """
    An expression's syntax tree, and what it says.
    """

    expression: libcst.BaseExpression
    """
    The expression.
    """

    @property
    def final_name(self) -> str | None:
        """
        The last name the expression refers to: ``read_text`` for ``path.read_text``,
        ``dict`` for ``dict[str, int]``; ``None`` when it refers to no name.
        """
        expression = self.expression
        if isinstance(expression, libcst.Name):
            return expression.value
        if isinstance(expression, libcst.Attribute):
            return expression.attr.value
        if isinstance(expression, libcst.Subscript):
            return ExpressionSyntax(expression.value).final_name
        return None

    @property
    def is_constant(self) -> bool:
        """
        Whether the expression is a literal number, string, bytes or ellipsis, or a
        :class:`ConstantName`.
        """
        expression = self.expression
        if isinstance(expression, libcst.Name):
            return expression.value in tuple(ConstantName)
        if isinstance(expression, libcst.ConcatenatedString):
            return expression.evaluated_value is not None
        return isinstance(
            expression,
            libcst.SimpleString
            | libcst.Integer
            | libcst.Float
            | libcst.Imaginary
            | libcst.Ellipsis,
        )

    @property
    def literal_text(self) -> str | None:
        """
        The text a literal string expression evaluates to; ``None`` for any other
        expression, a bytes literal and a formatted string included.
        """
        expression = self.expression
        if not isinstance(expression, libcst.SimpleString | libcst.ConcatenatedString):
            return None
        value = expression.evaluated_value
        return value if isinstance(value, str) else None


# %% calls


@dataclass(frozen=True)
class CallSyntax:
    """
    A call's syntax tree: the arguments it passes, and the call changed to pass others.
    """

    call: libcst.Call
    """
    The call.
    """

    @staticmethod
    def keyword_argument(keyword: str, value: libcst.BaseExpression) -> libcst.Arg:
        """
        :return: The argument passing *value* as *keyword*, with no space around its
            ``=``.
        """
        no_space = libcst.SimpleWhitespace("")
        return libcst.Arg(
            value,
            keyword=libcst.Name(keyword),
            equal=libcst.AssignEqual(
                whitespace_before=no_space, whitespace_after=no_space
            ),
        )

    def with_argument_appended(self, argument: libcst.Arg) -> libcst.Call:
        """
        :return: The call passing *argument* after its other arguments, laid out as
            they are: where a trailing comma ends them, it ends *argument* instead.
        """
        arguments = self.call.args
        if not arguments or not isinstance(arguments[-1].comma, libcst.Comma):
            return self.call.with_changes(args=[*arguments, argument])
        last = arguments[-1]
        whitespace_before_last = (
            arguments[-2].comma.whitespace_after
            if len(arguments) > 1
            else self.call.whitespace_before_args
        )
        return self.call.with_changes(
            args=[
                *arguments[:-1],
                last.with_changes(
                    comma=last.comma.with_changes(
                        whitespace_after=whitespace_before_last
                    )
                ),
                argument.with_changes(comma=last.comma),
            ]
        )

    def with_argument_replaced(
        self, original: libcst.Arg, replacement: libcst.Arg
    ) -> libcst.Call:
        """
        :param original: An argument of the call.
        :return: The call passing *replacement* in place of *original*, keeping the
            comma and whitespace around *original*.
        """
        return libcst.ensure_type(
            self.call.deep_replace(
                original,
                original.with_changes(
                    keyword=replacement.keyword, value=replacement.value
                ),
            ),
            libcst.Call,
        )


# %% bodies


@dataclass(frozen=True)
class BodySyntax:
    """
    The statements of a module, class or function body, one by one.
    """

    body: libcst.Module | libcst.BaseSuite
    """
    The module, or the suite of a class or function.
    """

    @cached_property
    def statements(self) -> tuple[libcst.CSTNode, ...]:
        """
        The statements of the body in order, those sharing a line included.
        """
        statements: list[libcst.CSTNode] = []
        for statement in self.body.body:
            if isinstance(statement, libcst.SimpleStatementLine):
                statements.extend(statement.body)
                continue
            statements.append(statement)
        return tuple(statements)

    @staticmethod
    def is_string(statement: libcst.CSTNode) -> bool:
        """
        :return: Whether *statement* is a bare string literal.
        """
        return (
            isinstance(statement, libcst.Expr)
            and ExpressionSyntax(statement.value).literal_text is not None
        )
