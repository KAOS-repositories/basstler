"""
Finds docstrings and comment blocks whose prose runs longer than a line limit.
"""

from __future__ import annotations

import inspect
import io
import re
import tokenize
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import override

import libcst
from libcst.metadata import CodeRange

from basstler.class_property import classproperty
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.syntax import BodySyntax, ExpressionSyntax
from basstler.code_rules.checker import CodeRuleChecker, CodeRuleViolation
from basstler.regular_expression import (
    Anchor,
    CharacterClass,
    CharacterSet,
    RegularExpression,
)
from basstler.text_file import TextFile

# %% what is measured


class ProseKind(StrEnum):
    """
    The kinds of prose measured.
    """

    DOCSTRING = "docstring"
    """
    A module, class, function or attribute docstring.
    """

    COMMENT = "comment block"
    """
    A run of consecutive lines holding only a comment.
    """


class ToolDirective(StrEnum):
    """
    What a comment addressed to a tool starts with, after its comment marker.
    """

    LINT_SUPPRESSION = "noqa"
    """
    Silences a linter finding on its line.
    """

    TYPE_COMMENT = "type:"
    """
    Gives a type checker a type or silences it.
    """

    PRAGMA = "pragma"
    """
    Instructs a coverage or other tool.
    """

    FORMATTER = "fmt:"
    """
    Switches the formatter off or on.
    """

    RUFF = "ruff:"
    """
    Configures ruff for the file.
    """

    INTERPRETER = "!"
    """
    Names the interpreter, in a script's first line.
    """

    ENCODING = "-*-"
    """
    Declares the file's encoding.
    """


@dataclass(frozen=True)
class ProseBlock:
    """
    One docstring or run of comment lines in a source file.
    """

    kind: ProseKind
    """
    Whether the block is a docstring or a comment block.
    """

    first_line: int
    """
    The block's first line in the file, counting from one.
    """

    last_line: int
    """
    The block's last line in the file, counting from one.
    """

    prose_lines: int
    """
    How many of its lines are prose: for a docstring, the non-blank lines before its
    field list that are neither indented below its own margin, such as a literal block,
    nor part of an example, from its ``>>>`` to the next blank line.
    """


@dataclass(frozen=True)
class SourceProse:
    """
    The docstrings and comment blocks of one Python source.
    """

    source: str
    """
    The text of the Python source.
    """

    @classproperty
    def field_list_item(cls) -> re.Pattern[str]:
        """
        A reStructuredText field, which starts a docstring's field list.

        >>> SourceProse.field_list_item.match(":param name: The name.")[0]
        ':param name:'
        """
        return RegularExpression.sequence(
            Anchor.LINE_START,
            ":",
            CharacterSet.any_except(":", CharacterClass.WHITESPACE),
            CharacterSet.any_except(":").zero_or_more(),
            ":",
        ).compiled()

    @classproperty
    def tool_directive(cls) -> re.Pattern[str]:
        """
        A comment addressed to a tool rather than a reader.

        >>> pattern = SourceProse.tool_directive
        >>> comments = ("# noqa: E501", "# the noqa rule")
        >>> [bool(pattern.match(comment)) for comment in comments]
        [True, False]
        """
        return RegularExpression.sequence(
            Anchor.LINE_START,
            "#",
            CharacterClass.WHITESPACE.zero_or_more(),
            RegularExpression.either(*ToolDirective),
        ).compiled()

    @property
    def blocks(self) -> list[ProseBlock]:
        """
        Every docstring and comment block, in no particular order.
        """
        return [*self.docstrings(), *self.comment_blocks()]

    def docstrings(self) -> Iterator[ProseBlock]:
        """
        :return: The docstring of the module and of every class and function, and every
            attribute docstring directly below an assignment in a module or class body.
        """
        module = PositionedModule(libcst.parse_module(self.source))
        for node in module.positions:
            if not isinstance(node, libcst.ClassDef | libcst.FunctionDef):
                continue
            yield from self.docstrings_of_body(module, node, BodySyntax(node.body))
        yield from self.docstrings_of_body(
            module, module.module, BodySyntax(module.module)
        )

    def docstrings_of_body(
        self, module: PositionedModule, owner: libcst.CSTNode, body: BodySyntax
    ) -> Iterator[ProseBlock]:
        """
        :param owner: The module, class or function whose body *body* is.
        :return: The docstrings among the statements of *body*.
        """
        for index, statement in enumerate(body.statements):
            if not BodySyntax.is_string(statement):
                continue
            follows_assignment = index > 0 and isinstance(
                body.statements[index - 1], libcst.Assign | libcst.AnnAssign
            )
            if index == 0 or (
                follows_assignment
                and isinstance(owner, libcst.Module | libcst.ClassDef)
            ):
                yield self.docstring_block(
                    libcst.ensure_type(statement, libcst.Expr),
                    module.positions[statement],
                )

    @staticmethod
    def docstring_block(statement: libcst.Expr, location: CodeRange) -> ProseBlock:
        """
        :param statement: A bare string literal.
        :param location: Where it lies in the source.
        :return: It, measured as a docstring.
        """
        prose_lines = 0
        in_example = False
        text = ExpressionSyntax(statement.value).literal_text
        for line in inspect.cleandoc(text or "").splitlines():
            if SourceProse.field_list_item.match(line):
                break
            in_example = bool(line.strip()) and (in_example or line.startswith(">>>"))
            if line.strip() and not line[0].isspace() and not in_example:
                prose_lines += 1
        return ProseBlock(
            ProseKind.DOCSTRING, location.start.line, location.end.line, prose_lines
        )

    def comment_blocks(self) -> Iterator[ProseBlock]:
        """
        :return: Every run of consecutive lines holding only a comment, section headers
            and comments addressed to tools left out.
        """
        lines: list[int] = []
        for token in tokenize.generate_tokens(io.StringIO(self.source).readline):
            if token.type != tokenize.COMMENT or token.line.strip() != token.string:
                continue
            if token.string.startswith("# %%") or self.tool_directive.match(
                token.string
            ):
                continue
            if lines and token.start[0] != lines[-1] + 1:
                yield ProseBlock(ProseKind.COMMENT, lines[0], lines[-1], len(lines))
                lines = []
            lines.append(token.start[0])
        if lines:
            yield ProseBlock(ProseKind.COMMENT, lines[0], lines[-1], len(lines))


# %% the check


@dataclass(frozen=True)
class ProseLengthChecker(CodeRuleChecker):
    """
    Finds the docstrings and comment blocks holding more prose lines than their limit.
    """

    docstring_lines: int = 4
    """
    The most prose lines a docstring may hold.
    """

    comment_lines: int = 3
    """
    The most lines a comment block may hold.
    """

    def limit_for(self, kind: ProseKind) -> int:
        """
        :return: The most prose lines a block of *kind* may hold.
        """
        return (
            self.docstring_lines if kind is ProseKind.DOCSTRING else self.comment_lines
        )

    @override
    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        for block in SourceProse(TextFile(path).read()).blocks:
            limit = self.limit_for(block.kind)
            if block.prose_lines <= limit:
                continue
            yield CodeRuleViolation(
                path,
                block.first_line,
                block.last_line,
                f"{block.kind} has {block.prose_lines} lines of prose, more than "
                f"{limit}; shorten it",
            )
