"""
Receivers asked about by a triage, the files that ask a type checker for their classes,
and the inference that answers with what it revealed.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import IntEnum

from basstler.experiments.receiver_inference.type_checkers import (
    RevealedType,
    SourcePosition,
)
from basstler.review_triage.calls import CallScope, ReceiverInference
from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.renames import RenameMap
from basstler.review_triage.signatures import SignatureReader

REVEAL_FUNCTION = "reveal_type"
"""
The function every type checker answers with the type of its argument.
"""

REVEAL_OPENING = f"{REVEAL_FUNCTION}("
"""
What a probe inserts before an expression whose type it asks for.
"""

REVEAL_CLOSING = ")"
"""
What a probe inserts after it.
"""

LINE_END = "\n"
"""
What ends a line, as Python's parser counts lines; other characters
:meth:`str.splitlines` splits at, such as a form feed, do not.
"""

# %% one receiver


@dataclass(frozen=True, order=True)
class ExpressionSpan:
    """
    Where an expression of a file is, in characters.
    """

    line: int
    """
    The line it starts on, counted from one.
    """

    column: int
    """
    The column it starts at, counted from zero.
    """

    end_line: int
    """
    The line it ends on.
    """

    end_column: int
    """
    The column after its last character.
    """

    @classmethod
    def of(cls, expression: ast.expr, text: str) -> ExpressionSpan:
        """
        :param expression: An expression parsed from the text, with positions.
        :param text: The file's text.
        :return: Its span, its byte offsets turned into characters.
        """
        lines = text.split(LINE_END)

        def characters(line: int, offset: int) -> int:
            return len(lines[line - 1].encode("utf-8")[:offset].decode("utf-8"))

        end_line = expression.end_lineno or expression.lineno
        end_offset = expression.end_col_offset or expression.col_offset
        return cls(
            expression.lineno,
            characters(expression.lineno, expression.col_offset),
            end_line,
            characters(end_line, end_offset),
        )

    def source_in(self, text: str) -> str:
        """
        :param text: The file's text.
        :return: The expression's source.
        """
        lines = text.split(LINE_END)[self.line - 1 : self.end_line]
        lines[-1] = lines[-1][: self.end_column]
        lines[0] = lines[0][self.column :]
        return LINE_END.join(lines)


@dataclass(frozen=True)
class ReceiverQuestion:
    """
    A receiver whose class the triage asked for.
    """

    module: str
    """
    The base text of the file holding it.
    """

    span: ExpressionSpan
    """
    Where it is in that text.
    """

    @classmethod
    def from_method_calls(cls, module: str) -> frozenset[ReceiverQuestion]:
        """
        :param module: The base text of a file.
        :return: The receiver of every method call in it, every receiver a triage can
            ask about among them; none when it is not valid Python.
        """
        source = PythonSource(module)
        if not source.parses:
            return frozenset()
        return frozenset(
            cls(module, ExpressionSpan.of(node.func.value, module))
            for node in ast.walk(source.tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        )


# %% the triage's questions


@dataclass(frozen=True)
class NoInference(ReceiverInference):
    """
    Answers no receiver.
    """

    def receiver_class(
        self,
        receiver: ast.expr,
        scope: CallScope,
        reader: SignatureReader,
        renames: RenameMap,
    ) -> str | None:
        return None


@dataclass(frozen=True)
class AnswerRecording(ReceiverInference):
    """
    Answers as another inference does, recording each receiver whose file is known that
    it is asked about, and the class it answers each with that the base commit defines.
    """

    inference: ReceiverInference
    """
    The inference answering.
    """

    asked: set[ReceiverQuestion] = field(default_factory=set)
    """
    Every receiver asked about so far.
    """

    answers: dict[ReceiverQuestion, str] = field(default_factory=dict)
    """
    The class every receiver answered so far was answered with.
    """

    def receiver_class(
        self,
        receiver: ast.expr,
        scope: CallScope,
        reader: SignatureReader,
        renames: RenameMap,
    ) -> str | None:
        found = self.inference.receiver_class(receiver, scope, reader, renames)
        if scope.module is None:
            return found
        question = ReceiverQuestion(
            scope.module.text, ExpressionSpan.of(receiver, scope.module.text)
        )
        self.asked.add(question)
        if found is not None and reader.definitions.classes_named(found):
            self.answers[question] = found
        return found


@dataclass(frozen=True)
class RevealedInference(ReceiverInference):
    """
    Answers each receiver a type checker revealed one class for.
    """

    answers: dict[ReceiverQuestion, str]
    """
    The class revealed for each receiver.
    """

    def receiver_class(
        self,
        receiver: ast.expr,
        scope: CallScope,
        reader: SignatureReader,
        renames: RenameMap,
    ) -> str | None:
        if scope.module is None:
            return None
        span = ExpressionSpan.of(receiver, scope.module.text)
        return self.answers.get(ReceiverQuestion(scope.module.text, span))


# %% the probe of one file


class EditOrder(IntEnum):
    """
    Which of two insertions at the same place comes first.
    """

    CLOSING = 0
    """
    Closing an expression that ends there, before opening one starting there.
    """

    OPENING = 1
    """
    Opening an expression that starts there.
    """


@dataclass(frozen=True, order=True)
class Insertion:
    """
    Text a probe inserts at one place of a line.
    """

    column: int
    """
    Where it is inserted, in characters.
    """

    order: EditOrder
    """
    Whether it closes or opens an expression.
    """

    nesting: int
    """
    Among insertions of one order at one place, the outer expression's opening first
    and the inner expression's closing first.
    """

    span: ExpressionSpan
    """
    The expression it belongs to.
    """


@dataclass(frozen=True)
class FileProbe:
    """
    A file's text with each receiver asked about wrapped in ``reveal_type(...)``, and
    where each one's argument ends up.
    """

    path: str
    """
    The file's path relative to the checkout.
    """

    text: str
    """
    The probe's text, as many lines as the file's.
    """

    arguments: dict[SourcePosition, ExpressionSpan]
    """
    The receiver each ``reveal_type`` argument starting at a position wraps.
    """

    @classmethod
    def of(cls, path: str, text: str, spans: list[ExpressionSpan]) -> FileProbe:
        """
        :param path: The file's path relative to the checkout.
        :param text: The file's text.
        :param spans: The receivers asked about in it.
        :return: The probe wrapping each of them.
        """
        insertions: dict[int, list[Insertion]] = {}
        for span in spans:
            size = (span.end_line - span.line, span.end_column - span.column)
            nesting = size[0] * len(text) + size[1]
            insertions.setdefault(span.line, []).append(
                Insertion(span.column, EditOrder.OPENING, -nesting, span)
            )
            insertions.setdefault(span.end_line, []).append(
                Insertion(span.end_column, EditOrder.CLOSING, nesting, span)
            )
        lines = text.split(LINE_END)
        arguments: dict[SourcePosition, ExpressionSpan] = {}
        for number, edits in insertions.items():
            line = lines[number - 1]
            probed = ""
            copied = 0
            for insertion in sorted(edits):
                probed += line[copied : insertion.column]
                copied = insertion.column
                if insertion.order is EditOrder.CLOSING:
                    probed += REVEAL_CLOSING
                    continue
                probed += REVEAL_OPENING
                arguments[SourcePosition(path, number, len(probed))] = insertion.span
            lines[number - 1] = probed + line[copied:]
        return cls(path, LINE_END.join(lines), arguments)

    def answers(
        self, module: str, revealed: list[RevealedType]
    ) -> dict[ReceiverQuestion, str]:
        """
        :param module: The base text of the file.
        :param revealed: The types a checker revealed in the probe, of any file.
        :return: The class revealed for each receiver of this file revealed as one.
        """
        return {
            ReceiverQuestion(module, self.arguments[found.position]): class_name
            for found in revealed
            if found.position in self.arguments
            and (class_name := found.instance_class) is not None
        }
