"""
Finds commands that start bash by its name instead of through
:class:`basstler.bash.Bash`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import override

import libcst
from libcst import matchers

from basstler.bash import Bash, LocatedProgram
from basstler.class_property import classproperty
from basstler.code_modification.patterns import CodePattern
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.syntax import ExpressionSyntax
from basstler.code_rules.checker import CodeRuleViolation
from basstler.code_rules.subprocess_function import SubprocessFunction
from basstler.code_rules.syntax_tree_checker import SyntaxTreeChecker

# %% the patterns


class BashCommandLine(CodePattern):
    """
    A list or tuple whose first element is the bare name of bash.
    """

    @classproperty
    def matcher(cls) -> matchers.OneOf:
        bash_first = [
            matchers.Element(
                value=matchers.MatchIfTrue(
                    lambda value: (
                        ExpressionSyntax(value).literal_text == LocatedProgram.BASH
                    )
                )
            ),
            matchers.ZeroOrMore(),
        ]
        return matchers.OneOf(
            matchers.List(elements=bash_first), matchers.Tuple(elements=bash_first)
        )


class BashStarted(CodePattern):
    """
    A call to a :mod:`subprocess` function, or a return, that hands on a command line
    starting bash by its name; the command line is saved as :attr:`saved_command_name`.
    """

    @classproperty
    def saved_command_name(cls) -> str:
        """
        The name the command line is saved under when the pattern matches.
        """
        return "command"

    @classproperty
    def matcher(cls) -> matchers.OneOf:
        command = matchers.SaveMatchedNode(
            BashCommandLine.matcher, cls.saved_command_name
        )
        return matchers.OneOf(
            matchers.Return(value=command),
            matchers.Call(
                func=SubprocessFunction.matcher,
                args=[matchers.Arg(value=command), matchers.ZeroOrMore()],
            ),
        )


# %% the check


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
        for occurrence in BashStarted.found_in(module):
            command = BashStarted.captures(occurrence.node, module.metadata)[
                BashStarted.saved_command_name
            ]
            location = module.positions[libcst.ensure_type(command, libcst.CSTNode)]
            yield CodeRuleViolation(
                path,
                location.start.line,
                location.end.line,
                f"starts {LocatedProgram.BASH} by its name, which Windows resolves to "
                f"WSL's launcher; build the command with {Bash.__name__}.locate(...)"
                f".{Bash.command.__name__}(...)",
            )
