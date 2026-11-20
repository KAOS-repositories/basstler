"""
Finds commands that start bash by its name instead of through :class:`basstler.bash.Bash`.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import override

import libcst

from basstler.bash import Bash, LocatedProgram
from basstler.code_rules.checker import CodeRuleChecker, CodeRuleViolation
from basstler.code_rules.source_module import SourceModule

# %% the check


@dataclass(frozen=True)
class BashByNameChecker(CodeRuleChecker):
    """
    Finds command lines whose program is bash given by its name, which Windows resolves
    to WSL's launcher: those passed to a :mod:`subprocess` function, and those returned.
    """

    @override
    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        module = SourceModule(path)
        for command in self.command_lines(module):
            if not self.starts_bash_by_name(command):
                continue
            yield CodeRuleViolation(
                path,
                module.first_line(command),
                module.last_line(command),
                f"starts {LocatedProgram.BASH} by its name, which Windows resolves to "
                f"WSL's launcher; build the command with {Bash.__name__}.locate(...)"
                f".{Bash.command.__name__}(...)",
            )

    @staticmethod
    def command_lines(module: SourceModule) -> Iterator[libcst.BaseExpression]:
        """
        :return: The command line each :mod:`subprocess` call in *module* runs, taken as
            its first argument, and every value it returns.
        """
        for statement in module.returns():
            if statement.value is not None:
                yield statement.value
        for call in module.calls():
            if call.args and module.refers_to(call.func, subprocess.__name__):
                yield call.args[0].value

    @staticmethod
    def starts_bash_by_name(command: libcst.BaseExpression) -> bool:
        """
        :return: Whether *command* is a list or tuple whose first element is the bare
            name of bash.
        """
        if not isinstance(command, libcst.List | libcst.Tuple) or not command.elements:
            return False
        first = command.elements[0].value
        return (
            isinstance(first, libcst.SimpleString)
            and first.evaluated_value == LocatedProgram.BASH
        )
