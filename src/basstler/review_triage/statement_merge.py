"""
A version of a Python file between two others: the later version's text of every
statement whose change the triage proves mechanical, the earlier version's elsewhere.
"""

from __future__ import annotations

import ast
import copy
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from functools import cached_property

from basstler.git.commit_range import FileVersions
from basstler.review_triage.comparison import FileTriager, MechanicalFile
from basstler.review_triage.python_source import PythonSource

# %% the lines statements occupy


@dataclass(frozen=True)
class LineReplacement:
    """
    Lines of the earlier version replaced by text of the later one.
    """

    first: int
    """
    The first line replaced, counted from one.
    """

    end: int
    """
    The line after the last one replaced; :attr:`first` when nothing is replaced and
    the text is inserted before that line.
    """

    text: str
    """
    The text replacing them, whole lines.
    """


@dataclass(frozen=True)
class StatementLines:
    """
    A statement of a block, with the blank lines and comments between it and the
    statement before it.
    """

    statement: ast.stmt
    """
    The statement.
    """

    first: int
    """
    The first of its lines, counted from one.
    """

    end: int
    """
    The line after its last.
    """


@dataclass(frozen=True)
class MergeCandidate:
    """
    A replacement worth trying, and the finer ones to try when it is not mechanical.
    """

    replacement: LineReplacement | None
    """
    The replacement, ``None`` when only the finer ones can be tried.
    """

    finer: tuple[MergeCandidate, ...] = ()
    """
    Replacements of parts of the same lines.
    """


DEFINITION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
"""
The statements holding a block of statements of their own that is merged statement by
statement.
"""

IMPORT_TYPES = (ast.Import, ast.ImportFrom)
"""
The import statements, which a module may gain or lose and still change mechanically.
"""

# %% pairing the two versions' statements


@dataclass(frozen=True)
class StatementAlignment:
    """
    Pairs the statements of two versions of a Python file by their code, and lists
    the replacements of the earlier version's statements worth trying.
    """

    earlier: PythonSource
    """
    The earlier version, ending in a newline.
    """

    later: PythonSource
    """
    The later version, ending in a newline.
    """

    @cached_property
    def earlier_lines(self) -> tuple[str, ...]:
        """
        The earlier version's lines, each with its line end.
        """
        return tuple(self.earlier.text.splitlines(keepends=True))

    @cached_property
    def later_lines(self) -> tuple[str, ...]:
        """
        The later version's lines, each with its line end.
        """
        return tuple(self.later.text.splitlines(keepends=True))

    def candidates(self) -> tuple[MergeCandidate, ...]:
        """
        :return: The replacements to try, in the order of the file.
        """
        return self.block_candidates(
            self.earlier.tree.body, self.later.tree.body, 1, 1, is_module=True
        )

    def block_candidates(
        self,
        earlier_block: list[ast.stmt],
        later_block: list[ast.stmt],
        earlier_first: int,
        later_first: int,
        is_module: bool = False,
    ) -> tuple[MergeCandidate, ...]:
        """
        :param earlier_block: A block of statements of the earlier version.
        :param later_block: The block in the same place in the later version.
        :param earlier_first: The first line of the earlier block's first statement.
        :param later_first: The first line of the later block's first statement.
        :param is_module: Whether the blocks are the modules' own statements, which
            may gain and lose imports.
        :return: The replacements of the earlier block's statements to try.
        """
        earlier = self.statement_lines(earlier_block, earlier_first)
        later = self.statement_lines(later_block, later_first)
        if earlier is None or later is None:
            return ()
        matcher = SequenceMatcher(
            None,
            [self.code_of(each.statement) for each in earlier],
            [self.code_of(each.statement) for each in later],
            autojunk=False,
        )
        candidates: list[MergeCandidate | None] = []
        for (
            tag,
            earlier_start,
            earlier_end,
            later_start,
            later_end,
        ) in matcher.get_opcodes():
            earlier_part = earlier[earlier_start:earlier_end]
            later_part = later[later_start:later_end]
            if tag == "equal":
                candidates += [
                    self.pair_candidate(first, second, replace_whole=True)
                    for first, second in zip(earlier_part, later_part, strict=True)
                ]
            elif is_module and self.only_imports(earlier_part + later_part):
                candidates.append(
                    self.imports_candidate(
                        earlier, earlier_start, earlier_part, later_part
                    )
                )
            else:
                candidates += [
                    self.pair_candidate(first, second, replace_whole=False)
                    for first, second in self.definition_pairs(earlier_part, later_part)
                ]
        return tuple(candidate for candidate in candidates if candidate is not None)

    @staticmethod
    def statement_lines(
        block: list[ast.stmt], first: int
    ) -> tuple[StatementLines, ...] | None:
        """
        :param block: A block of statements.
        :param first: The first line of its first statement.
        :return: Each statement's lines, ``None`` when two of them share a line.
        """
        lines: list[StatementLines] = []
        start = first
        for statement in block:
            if StatementAlignment.first_line(statement) < start:
                return None
            end = (statement.end_lineno or statement.lineno) + 1
            lines.append(StatementLines(statement, start, end))
            start = end
        return tuple(lines)

    @staticmethod
    def first_line(statement: ast.stmt) -> int:
        """
        :param statement: A statement.
        :return: Its first line, its decorators included.
        """
        decorators = (
            statement.decorator_list if isinstance(statement, DEFINITION_TYPES) else []
        )
        return min([statement.lineno, *(node.lineno for node in decorators)])

    @staticmethod
    def code_of(statement: ast.stmt) -> str:
        """
        :param statement: A statement.
        :return: Its code as the triage compares it, an import as it is written.
        """
        if isinstance(statement, IMPORT_TYPES):
            return ast.dump(statement)
        module = ast.Module([copy.deepcopy(statement)], [])
        PythonSource.strip_to_code(module)
        return ast.dump(module)

    @staticmethod
    def only_imports(lines: tuple[StatementLines, ...]) -> bool:
        """
        :param lines: Statements of a module.
        :return: Whether there are any and they are all imports.
        """
        return bool(lines) and all(
            isinstance(each.statement, IMPORT_TYPES) for each in lines
        )

    @staticmethod
    def definition_pairs(
        earlier: tuple[StatementLines, ...], later: tuple[StatementLines, ...]
    ) -> list[tuple[StatementLines, StatementLines]]:
        """
        :param earlier: Statements of the earlier version that differ.
        :param later: The statements of the later version in their place.
        :return: Each earlier definition with the later one of the same kind and name.
        """
        later_definitions = {
            (type(each.statement), each.statement.name): each
            for each in later
            if isinstance(each.statement, DEFINITION_TYPES)
        }
        return [
            (each, partner)
            for each in earlier
            if isinstance(each.statement, DEFINITION_TYPES)
            and (
                partner := later_definitions.get(
                    (type(each.statement), each.statement.name)
                )
            )
            is not None
        ]

    def pair_candidate(
        self, earlier: StatementLines, later: StatementLines, replace_whole: bool
    ) -> MergeCandidate | None:
        """
        :param earlier: A statement of the earlier version.
        :param later: The statement in its place in the later version.
        :param replace_whole: Whether to try replacing the whole statement first.
        :return: What to try, ``None`` when nothing differs or the two are indented
            differently.
        """
        text = self.text_of(later.first, later.end)
        earlier_text = "".join(self.earlier_lines[earlier.first - 1 : earlier.end - 1])
        if (
            earlier_text == text
            or earlier.statement.col_offset != later.statement.col_offset
        ):
            return None
        finer: tuple[MergeCandidate, ...] = ()
        if isinstance(earlier.statement, DEFINITION_TYPES) and isinstance(
            later.statement, type(earlier.statement)
        ):
            finer = self.block_candidates(
                earlier.statement.body,
                later.statement.body,
                self.first_line(earlier.statement.body[0]),
                self.first_line(later.statement.body[0]),
            )
        whole = LineReplacement(earlier.first, earlier.end, text)
        return MergeCandidate(whole if replace_whole else None, finer)

    def imports_candidate(
        self,
        earlier: tuple[StatementLines, ...],
        earlier_start: int,
        earlier_part: tuple[StatementLines, ...],
        later_part: tuple[StatementLines, ...],
    ) -> MergeCandidate:
        """
        :param earlier: Every statement of the earlier module.
        :param earlier_start: The index of the first of *earlier_part* in it.
        :param earlier_part: Imports of the earlier module that differ, maybe none.
        :param later_part: The imports in their place in the later module, maybe none.
        :return: Replacing the earlier imports by the later ones.
        """
        if earlier_part:
            first, end = earlier_part[0].first, earlier_part[-1].end
        elif earlier_start < len(earlier):
            first = end = earlier[earlier_start].first
        else:
            first = end = earlier[-1].end
        text = (
            self.text_of(later_part[0].first, later_part[-1].end) if later_part else ""
        )
        return MergeCandidate(LineReplacement(first, end, text))

    def text_of(self, first: int, end: int) -> str:
        """
        :param first: A line of the later version, counted from one.
        :param end: The line after the last one wanted.
        :return: Those lines' text.
        """
        return "".join(self.later_lines[first - 1 : end - 1])


# %% the merged version


@dataclass(frozen=True)
class StatementMerge:
    """
    Builds the version of a file taking every mechanical statement change of its head
    version onto a starting version.
    """

    triager: FileTriager
    """
    Judges whether a version differs from the file's base only mechanically.
    """

    change: FileVersions
    """
    The file's change, whose base version every merged version is judged against.
    """

    def merged_text(self, start: str) -> str:
        """
        :param start: A version of the file differing from its base only
            mechanically.
        :return: *start* with every statement change of the head version taken that
            keeps it mechanical, each tried whole before its parts, without the
            whitespace around it, as git reads a file back.
        """
        earlier = PythonSource(f"{start}\n")
        later = PythonSource(f"{self.change.head_text}\n")
        accepted: list[LineReplacement] = []
        for candidate in StatementAlignment(earlier, later).candidates():
            self.adopt(earlier.text, candidate, accepted)
        return self.applied(earlier.text, accepted).strip()

    def adopt(
        self, start: str, candidate: MergeCandidate, accepted: list[LineReplacement]
    ) -> None:
        """
        Add to *accepted* the candidate's replacement when it keeps the file
        mechanical, otherwise those of its finer candidates that do.

        :param start: The version the replacements apply to.
        :param candidate: The replacement to try.
        :param accepted: The replacements taken so far.
        """
        replacement = candidate.replacement
        if replacement is not None and self.is_mechanical(
            self.applied(start, [*accepted, replacement])
        ):
            accepted.append(replacement)
            return
        for finer in candidate.finer:
            self.adopt(start, finer, accepted)

    def is_mechanical(self, text: str) -> bool:
        """
        :param text: A version of the file.
        :return: Whether, read back from git without the whitespace around it, it
            differs from the file's base only mechanically.
        """
        version = text.strip()
        if version == self.change.base_text:
            return True
        verdict = self.triager.triage(replace(self.change, head_text=version))
        return isinstance(verdict, MechanicalFile)

    @staticmethod
    def applied(text: str, replacements: list[LineReplacement]) -> str:
        """
        :param text: A version of the file, ending in a newline.
        :param replacements: Replacements of its lines that do not overlap.
        :return: The version with them made.
        """
        lines = text.splitlines(keepends=True)
        for replacement in sorted(
            replacements, key=lambda each: (each.first, each.end), reverse=True
        ):
            lines[replacement.first - 1 : replacement.end - 1] = [replacement.text]
        return "".join(lines)
