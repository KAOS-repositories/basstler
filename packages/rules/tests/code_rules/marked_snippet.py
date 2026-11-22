"""
A source snippet whose offending lines are marked in the snippet itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from pathlib import Path

from basstler.code_rules.checker import CodeRuleChecker

# %% the marker


class ViolationMarker(StrEnum):
    """
    The comment ending each line of a snippet that a checker must report.
    """

    COMMENT = "# violation"
    """
    Written at the end of the first line of the offending code.
    """


# %% the snippet


@dataclass(frozen=True)
class MarkedSnippet:
    """
    A snippet that shows, line by line, what its checker is expected to report.
    """

    path: Path
    """
    The snippet's source file.
    """

    @cached_property
    def marked_lines(self) -> list[int]:
        """
        :return: The numbers of the lines ending in :attr:`ViolationMarker.COMMENT`,
            counting from one.
        """
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [
            number
            for number, line in enumerate(lines, start=1)
            if line.endswith(ViolationMarker.COMMENT)
        ]

    def reported_lines(self, checker: CodeRuleChecker) -> list[int]:
        """
        :return: The first line of each violation *checker* reports in the snippet.
        """
        return [violation.first_line for violation in checker.violations(self.path)]
