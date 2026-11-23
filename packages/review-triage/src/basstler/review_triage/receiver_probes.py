"""
The receivers of method calls in a pull request's changed files, the files asking a type
checker for their classes, and the classes it reveals.
"""

from __future__ import annotations

import ast
import tempfile
from dataclasses import dataclass
from enum import IntEnum
from functools import cached_property
from pathlib import Path, PurePosixPath

from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.commit_tree import PYTHON_FILE_PATTERNS, CommitModules
from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.type_checkers import (
    RevealedType,
    SourcePosition,
    TypeChecker,
)
from basstler.text_file import UTF_8, TextFile

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
        end_line = expression.end_lineno or expression.lineno
        end_offset = expression.end_col_offset or expression.col_offset
        return cls(
            expression.lineno,
            cls.characters(lines[expression.lineno - 1], expression.col_offset),
            end_line,
            cls.characters(lines[end_line - 1], end_offset),
        )

    @staticmethod
    def characters(line: str, offset: int) -> int:
        """
        :param line: A line of a file.
        :param offset: A position in its UTF-8 bytes, as :mod:`ast` counts columns.
        :return: The same position in characters.
        """
        return len(line.encode(UTF_8)[:offset].decode(UTF_8))

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


# %% the pull request's receivers


@dataclass(frozen=True)
class RevealedReceivers:
    """
    The classes a type checker reveals for the method call receivers of a pull
    request's changed Python files, in their base versions; the checker runs once, when
    the first receiver is asked for.
    """

    modules: CommitModules
    """
    The modules of the base commit.
    """

    paths: dict[str, str]
    """
    The path of each changed Python file, relative to the commit's root, by its base
    text.
    """

    checker: TypeChecker
    """
    The type checker asked.
    """

    @classmethod
    def from_changes(
        cls, changes: PullRequestChanges, checker: TypeChecker
    ) -> RevealedReceivers:
        """
        :param changes: A pull request and the files it changes.
        :param checker: The type checker to ask.
        :return: The receivers of its changed Python files, not revealed yet.
        """
        return cls(
            CommitModules(changes.commits.base_tree),
            cls.python_paths(changes),
            checker,
        )

    @staticmethod
    def python_paths(changes: PullRequestChanges) -> dict[str, str]:
        """
        :param changes: A pull request and the files it changes.
        :return: The base path of each changed Python file by its base text.
        """
        return {
            file.base_text: base_path.as_posix()
            for file in changes.files
            if file.base_text is not None
            and any(
                (base_path := file.previous_path or file.path).match(pattern)
                for pattern in PYTHON_FILE_PATTERNS
            )
        }

    @cached_property
    def questions(self) -> frozenset[ReceiverQuestion]:
        """
        The receiver of every method call in the changed files' base versions.
        """
        return frozenset(
            question
            for module in self.paths
            for question in ReceiverQuestion.from_method_calls(module)
        )

    @cached_property
    def probes(self) -> dict[str, FileProbe]:
        """
        The probe of each changed file, by its base text.
        """
        return {
            module: FileProbe.of(
                path,
                module,
                sorted(
                    question.span
                    for question in self.questions
                    if question.module == module
                ),
            )
            for module, path in self.paths.items()
        }

    @cached_property
    def classes(self) -> dict[ReceiverQuestion, str]:
        """
        The class revealed for each receiver revealed as an instance of one.

        :raises TypeCheckerFailed: If the checker fails to check the files.
        """
        if not self.questions:
            return {}
        with tempfile.TemporaryDirectory() as checkout:
            self.write_commit(Path(checkout))
            revealed = self.checker.reveal(
                sorted(probe.path for probe in self.probes.values()),
                [Path(checkout, root) for root in self.modules.import_roots],
                Path(checkout),
            )
        return {
            question: class_name
            for module, probe in self.probes.items()
            for question, class_name in probe.answers(module, revealed).items()
        }

    def write_commit(self, checkout: Path) -> None:
        """
        Write the base commit's Python files, each changed file as its probe.

        :param checkout: An empty directory.
        """
        names = {
            f"{self.modules.tree.commit}:{path.as_posix()}": path
            for path in sorted(self.modules.tree.file_paths)
            if any(path.match(pattern) for pattern in PYTHON_FILE_PATTERNS)
        }
        probed = {
            PurePosixPath(probe.path): probe.text for probe in self.probes.values()
        }
        texts = self.modules.tree.git.object_texts(tuple(names))
        for name, path in names.items():
            written = checkout / path
            written.parent.mkdir(parents=True, exist_ok=True)
            TextFile(written).write(probed.get(path, texts[name]))

    @cached_property
    def base_texts(self) -> dict[str, str]:
        """
        The base text of each changed Python file, by each text it is compared as whose
        lines keep their places: itself and itself without its module documentation.
        """
        sources = [PythonSource.from_text(module) for module in self.paths]
        return {
            compared.text: source.text
            for source in sources
            for compared in (
                (source, source.without_module_documentation)
                if source.parses
                else (source,)
            )
        }

    def class_of(self, receiver: ast.expr, compared_text: str) -> str | None:
        """
        :param receiver: The expression a method is called on.
        :param compared_text: The text of the file holding it, as the triage compares it.
        :return: The class revealed for it, ``None`` when none is or the text is no
            changed Python file's.
        """
        module = self.base_texts.get(compared_text)
        if module is None:
            return None
        return self.classes.get(
            ReceiverQuestion(module, ExpressionSpan.of(receiver, compared_text))
        )
