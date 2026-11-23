"""
The base of the checkers that read a module's concrete syntax tree.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import override

from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.source_file import EditablePythonSourceFile
from basstler.code_rules.checker import CodeRuleChecker, CodeRuleViolation

# %% the check


class SyntaxTreeChecker(CodeRuleChecker, ABC):
    """
    Finds the code that breaks one rule in a module parsed to a concrete syntax tree.
    """

    @abstractmethod
    def violations_of_module(
        self, path: Path, module: PositionedModule
    ) -> Iterator[CodeRuleViolation]:
        """
        :param path: The file *module* was parsed from.
        :param module: The module to check.
        :return: Every place in it that breaks the rule.
        """

    @override
    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        yield from self.violations_of_module(
            path, PositionedModule(EditablePythonSourceFile(path).parse())
        )
