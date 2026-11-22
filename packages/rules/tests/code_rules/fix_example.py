"""
The examples a fixable checker's fix is tested on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from basstler.code_rules.fixes import FixableChecker

from basstler_testing.constants.paths import RuleFixExample, RuleFixExampleFile


@dataclass(frozen=True)
class FixExample:
    """
    One example of a fix: code breaking its rule, and that code fixed.
    """

    checker: FixableChecker
    """
    The checker whose fix the example shows.
    """

    directory: Path
    """
    The directory holding the example's files.
    """

    @classmethod
    def all_of(cls, checker: FixableChecker) -> list[FixExample]:
        """
        :return: The examples of *checker*'s fix, in alphabetical order.
        """
        directory = RuleFixExample.DIRECTORY / type(checker).__name__
        if not directory.is_dir():
            return []
        return [cls(checker, example) for example in sorted(directory.iterdir())]

    @property
    def before(self) -> Path:
        """
        The code breaking the rule.
        """
        return self.directory / RuleFixExampleFile.BEFORE

    @property
    def after(self) -> Path:
        """
        The code once fixed.
        """
        return self.directory / RuleFixExampleFile.AFTER

    @property
    def identifier(self) -> str:
        """
        The example's name in a test's identifier.
        """
        return f"{type(self.checker).__name__}-{self.directory.name}"
