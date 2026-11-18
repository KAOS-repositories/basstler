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
import libcst.matchers as m

from basstler.bash import Bash, LocatedProgram
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.syntax import ExpressionSyntax
from basstler.code_rules.checker import CodeRuleViolation
from basstler.code_rules.syntax_tree_checker import SyntaxTreeChecker

# %% the check

SUBPROCESS_CALL = m.Call(
    func=m.Attribute(value=m.Name(subprocess.__name__)), args=[m.Arg(), m.ZeroOrMore()]
)
"""
A call to a :mod:`subprocess` function with at least one argument.
"""

BASH_FIRST = [
    m.Element(
        value=m.MatchIfTrue(
            lambda value: ExpressionSyntax(value).literal_text == LocatedProgram.BASH
        )
    ),
    m.ZeroOrMore(),
]
BASH_BY_NAME = m.OneOf(m.List(elements=BASH_FIRST), m.Tuple(elements=BASH_FIRST))
"""
A list or tuple whose first element is the bare name of bash.
"""


@dataclass(frozen=True)
class BashByNameChecker(SyntaxTreeChecker):
    """
    Finds command lines whose program is bash given by its name, which Windows resolves
    to WSL's launcher: those passed to a :mod:`subprocess` function, and those returned.
    """

    @override
    def violations_of_module(
        self, path: Path, module: PositionedModule
    ) -> Iterator[CodeRuleViolation]:
        for node in module.positions:
            command = self.command_line(node)
            if command is None or not m.matches(command, BASH_BY_NAME):
                continue
            location = module.positions[command]
            yield CodeRuleViolation(
                path,
                location.start.line,
                location.end.line,
                f"starts {LocatedProgram.BASH} by its name, which Windows resolves to "
                f"WSL's launcher; build the command with {Bash.__name__}.locate(...)"
                f".{Bash.command.__name__}(...)",
            )

    @staticmethod
    def command_line(node: libcst.CSTNode) -> libcst.BaseExpression | None:
        """
        :return: The command line *node* runs or hands on: the first argument of a call
            to a :mod:`subprocess` function, or a returned value; ``None`` otherwise.
        """
        if isinstance(node, libcst.Return):
            return node.value
        if m.matches(node, SUBPROCESS_CALL):
            return libcst.ensure_type(node, libcst.Call).args[0].value
        return None
