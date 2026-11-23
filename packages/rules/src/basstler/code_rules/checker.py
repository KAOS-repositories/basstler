"""
The base every code rule checker extends, and the violations checkers report.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from pathlib import Path

from basstler.class_property import classproperty
from basstler.git.commands import GitCommandRunner
from basstler.regular_expression import (
    Anchor,
    CharacterClass,
    RegularExpression,
    Wildcard,
)

# %% violations


@dataclass(frozen=True)
class CodeRuleViolation:
    """
    One place in a source file that breaks a rule.
    """

    path: Path
    """
    The file breaking the rule.
    """

    first_line: int
    """
    The first line of the offending code, counting from one.
    """

    last_line: int
    """
    The last line of the offending code, counting from one.
    """

    description: str
    """
    What is wrong and how to fix it, as one sentence fragment.
    """

    def touches(self, lines: set[int]) -> bool:
        """
        :param lines: Line numbers in the file.
        :return: Whether any of them falls within the offending code.
        """
        return any(self.first_line <= line <= self.last_line for line in lines)

    def render(self) -> str:
        """
        :return: The violation as it is printed.
        """
        return f"{self.path}:{self.first_line}: {self.description}"


# %% checkers


class CodeRuleChecker(ABC):
    """
    Finds the code that breaks one agent rule, the rule that names this checker.
    """

    @abstractmethod
    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        """
        :param path: A Python source file.
        :return: Every place in it that breaks the rule.
        """


# %% the staged change


class DiffHeaderGroup(StrEnum):
    """
    The parts of a diff header read back from its match.
    """

    STAGED_FILE = "staged_file"
    """
    The path of a file the change touches, after the change.
    """

    FIRST_LINE = "first_line"
    """
    The first line of a changed block, after the change.
    """

    LINE_COUNT = "line_count"
    """
    How many lines the changed block has after the change, absent for one line.
    """


@dataclass(frozen=True)
class StagedLines:
    """
    The lines a commit being prepared adds or changes.
    """

    git: GitCommandRunner
    """
    The repository the commit is prepared in.
    """

    def of(self, path: Path) -> set[int]:
        """
        :param path: A file in the repository.
        :return: The line numbers, in the staged file, that the staged change adds or
            changes; none for a file the change only moves.
        """
        return self.lines_by_file.get(path.resolve(), set())

    @classproperty
    def diff_header(cls) -> re.Pattern[str]:
        """
        A file's header, or a changed block's, in a diff without context lines.

        >>> pattern = StagedLines.diff_header
        >>> pattern.match("diff --git a/old.py b/new.py")[DiffHeaderGroup.STAGED_FILE]
        'new.py'
        >>> StagedLines.diff_header.match("@@ -3 +7,4 @@")[DiffHeaderGroup.FIRST_LINE]
        '7'
        """
        file_header = RegularExpression.sequence(
            Anchor.LINE_START,
            "diff --git a/",
            Wildcard.ANY_CHARACTER_EXCEPT_LINE_BREAK.one_or_more(),
            " b/",
            Wildcard.ANY_CHARACTER_EXCEPT_LINE_BREAK.one_or_more().captured_as(
                DiffHeaderGroup.STAGED_FILE
            ),
            Anchor.LINE_END,
        )
        line_count = RegularExpression.sequence(
            ",",
            CharacterClass.DIGIT.one_or_more().captured_as(DiffHeaderGroup.LINE_COUNT),
        )
        block_header = RegularExpression.sequence(
            Anchor.LINE_START,
            "@@ -",
            CharacterClass.NON_WHITESPACE.one_or_more(),
            " +",
            CharacterClass.DIGIT.one_or_more().captured_as(DiffHeaderGroup.FIRST_LINE),
            line_count.optional(),
            " @@",
        )
        return RegularExpression.either(file_header, block_header).compiled()

    @cached_property
    def lines_by_file(self) -> dict[Path, set[int]]:
        """
        :return: The lines the staged change adds or changes, by the staged file they
            are in, with moves detected so a moved file keeps its committed lines.
        """
        diff = self.git.run(
            "diff",
            "--cached",
            "--find-renames",
            "--unified=0",
            "--no-color",
            "--relative",
        )
        lines_by_file: dict[Path, set[int]] = {}
        lines: set[int] = set()
        for match in self.diff_header.finditer(diff):
            staged_file = match[DiffHeaderGroup.STAGED_FILE]
            if staged_file is not None:
                lines = lines_by_file.setdefault(
                    (self.git.working_directory / staged_file).resolve(), set()
                )
                continue
            start = int(match[DiffHeaderGroup.FIRST_LINE])
            line_count = match[DiffHeaderGroup.LINE_COUNT]
            count = 1 if line_count is None else int(line_count)
            lines.update(range(start, start + count))
        return lines_by_file


# %% checking files


@dataclass(frozen=True)
class CodeRulesCheck:
    """
    Runs a set of checkers over a set of files.
    """

    checkers: tuple[CodeRuleChecker, ...]
    """
    The checkers to run.
    """

    staged: StagedLines | None = None
    """
    The staged change whose code alone is checked, ``None`` to check all of it.
    """

    def violations(self, paths: Sequence[Path]) -> list[CodeRuleViolation]:
        """
        :param paths: The Python files to check.
        :return: Their violations, file by file, top to bottom.
        """
        violations: list[CodeRuleViolation] = []
        for path in paths:
            changed = None if self.staged is None else self.staged.of(path)
            found = [
                violation
                for checker in self.checkers
                for violation in checker.violations(path)
                if changed is None or violation.touches(changed)
            ]
            violations.extend(sorted(found, key=lambda violation: violation.first_line))
        return violations
