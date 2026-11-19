"""
Finds commands that start bash by its name instead of through :class:`basstler.bash.Bash`,
and fixes those that have an environment to locate it in.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import override

import libcst
from libcst import matchers

from basstler.bash import Bash, LocatedProgram
from basstler.class_property import classproperty
from basstler.code_modification.patterns import CodePattern
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.source_file import PythonSourceFile
from basstler.code_modification.specification import Specification
from basstler.code_modification.syntax import ExpressionSyntax
from basstler.code_rules.checker import CodeRuleViolation
from basstler.code_rules.commands import CodeRulesCommand
from basstler.code_rules.fixes import (
    BehaviourDeclaration,
    BehaviourEffect,
    CodeFix,
    FixableChecker,
)
from basstler.code_rules.subprocess_function import SubprocessFunction

# %% the patterns


class ScopedName(StrEnum):
    """
    The names the fix relies on being bound where it works.
    """

    ENVIRONMENT = "environment"
    """
    The parameter holding the environment the command runs in.
    """


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


@dataclass(frozen=True)
class StartedCommandLine:
    """
    A command line starting bash by its name, and whether the function around it can
    locate bash.
    """

    node: libcst.List | libcst.Tuple
    """
    The command line.
    """

    has_environment: bool
    """
    Whether the innermost function around the command line has an environment
    parameter.
    """


@dataclass
class CommandLineFinder(libcst.CSTVisitor):
    """
    Collects the command lines a module starts bash by its name with.
    """

    found: list[StartedCommandLine] = field(default_factory=list)
    """
    Each command line, in the order of the source.
    """

    scopes: list[bool] = field(default_factory=list)
    """
    For each function being visited, whether it has an environment parameter.
    """

    @override
    def visit_FunctionDef(self, node: libcst.FunctionDef) -> None:
        """
        Enter the function's scope, noting whether it has an environment parameter.
        """
        self.scopes.append(
            any(
                parameter.name.value == ScopedName.ENVIRONMENT
                for parameter in node.params.params
            )
        )

    @override
    def leave_FunctionDef(self, original_node: libcst.FunctionDef) -> None:
        """
        Leave the function's scope.
        """
        self.scopes.pop()

    @override
    def visit_Call(self, node: libcst.Call) -> None:
        """
        Collect the command line a :mod:`subprocess` function runs.
        """
        self.collect(node)

    @override
    def visit_Return(self, node: libcst.Return) -> None:
        """
        Collect the command line a function returns.
        """
        self.collect(node)

    def collect(self, node: libcst.CSTNode) -> None:
        """
        Keep the command line *node* hands on when it starts bash by its name.
        """
        captures = BashStarted.captures(node)
        if captures is None:
            return
        command = captures[BashStarted.saved_command_name]
        self.found.append(
            StartedCommandLine(
                libcst.ensure_type(command, libcst.List | libcst.Tuple),
                bool(self.scopes) and self.scopes[-1],
            )
        )


# %% the fix


class LocatedBashFix(CodeFix[Specification]):
    """
    Builds the command line with the bash :class:`basstler.bash.Bash` locates in the
    environment.
    """

    @classproperty
    def behaviour(cls) -> BehaviourDeclaration:
        return BehaviourDeclaration(
            BehaviourEffect.CHANGED,
            "The command starts the bash located in the environment, never WSL's "
            "launcher, and is a list where it was a tuple; nothing changes where the "
            "bash found by name is the located one.",
        )

    @classproperty
    def required_import(cls) -> type:
        """
        :class:`~basstler.bash.Bash`.
        """
        return Bash

    def replacement(self, specification: Specification) -> libcst.Call:
        command = libcst.ensure_type(specification.node, libcst.List | libcst.Tuple)
        arguments = [
            libcst.Arg(
                value=element.value,
                star="*" if isinstance(element, libcst.StarredElement) else "",
                comma=element.comma,
            )
            for element in command.elements[1:]
        ]
        locate = libcst.Call(
            func=libcst.Attribute(
                value=libcst.Name(Bash.__name__),
                attr=libcst.Name(Bash.locate.__name__),
            ),
            args=[libcst.Arg(libcst.Name(ScopedName.ENVIRONMENT))],
        )
        return libcst.Call(
            func=libcst.Attribute(
                value=locate, attr=libcst.Name(Bash.command.__name__)
            ),
            args=arguments,
        )


# %% the check


@dataclass(frozen=True)
class BashByNameChecker(FixableChecker[Specification]):
    """
    Finds command lines whose program is bash given by its name, which Windows resolves
    to WSL's launcher: those passed to a :mod:`subprocess` function, and those returned.
    """

    @classproperty
    def fix(cls) -> CodeFix[Specification]:
        return LocatedBashFix()

    @classproperty
    def violation_description(cls) -> str:
        return (
            f"starts {LocatedProgram.BASH} by its name, which Windows resolves to "
            f"WSL's launcher; build the command with {Bash.__name__}.locate(...)"
            f".{Bash.command.__name__}(...)"
        )

    @override
    def specifications_of_module(
        self, module: PositionedModule
    ) -> Iterator[Specification]:
        for command in self.command_lines(module):
            if command.has_environment:
                yield Specification(module.positions[command.node], command.node)

    @override
    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        """
        Also reports the command lines with no environment in scope, which no fix
        covers; :meth:`FixableChecker.violations`.
        """
        yield from super().violations(path)
        module = PositionedModule(PythonSourceFile(path).parse())
        for command in self.command_lines(module):
            if command.has_environment:
                continue
            location = module.positions[command.node]
            yield CodeRuleViolation(
                path,
                location.start.line,
                location.end.line,
                f"{self.violation_description}; no `{ScopedName.ENVIRONMENT}` is in "
                f"scope, so `{CodeRulesCommand.FIX.invocation}` leaves it",
            )

    @staticmethod
    def command_lines(module: PositionedModule) -> list[StartedCommandLine]:
        """
        :return: The command lines of *module* starting bash by its name.
        """
        finder = CommandLineFinder()
        module.module.visit(finder)
        return finder.found
