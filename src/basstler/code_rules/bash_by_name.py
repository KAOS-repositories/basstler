"""
Finds commands that start bash by its name instead of through :class:`basstler.bash.Bash`,
and fixes those that have an environment to locate it in.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import override

import libcst
from libcst.metadata import CodeRange

from basstler.bash import Bash, LocatedProgram
from basstler.class_property import classproperty
from basstler.code_modification.imports import ImportedName
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.specification import Specification
from basstler.code_rules.checker import CodeRuleViolation
from basstler.code_rules.commands import CodeRulesCommand
from basstler.code_rules.fixes import (
    BehaviourDeclaration,
    BehaviourEffect,
    CodeFix,
    FixableChecker,
)

# %% the places


class ScopedName(StrEnum):
    """
    The names the fix relies on being bound where it works.
    """

    ENVIRONMENT = "environment"
    """
    The parameter holding the environment the command runs in.
    """


@dataclass(frozen=True)
class BashCommandLine(Specification):
    """
    A command line starting with bash given by its name, in a function that has the
    environment to locate bash in.
    """

    node: libcst.List | libcst.Tuple
    """
    The command line, whose first element is the name of bash.
    """


@dataclass
class CommandLineFinder(libcst.CSTVisitor):
    """
    Collects the command lines a module runs or returns that start with bash by name.
    """

    found: list[tuple[libcst.List | libcst.Tuple, bool]] = field(default_factory=list)
    """
    Each command line, and whether the function around it has an environment parameter.
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
        function = node.func
        if (
            isinstance(function, libcst.Attribute)
            and isinstance(function.value, libcst.Name)
            and function.value.value == subprocess.__name__
            and node.args
        ):
            self.collect(node.args[0].value)

    @override
    def visit_Return(self, node: libcst.Return) -> None:
        """
        Collect the command line a function returns.
        """
        if node.value is not None:
            self.collect(node.value)

    def collect(self, command: libcst.BaseExpression) -> None:
        """
        Keep *command* when it is a list or tuple starting with the name of bash.
        """
        if not isinstance(command, libcst.List | libcst.Tuple) or not command.elements:
            return
        first = command.elements[0].value
        if (
            isinstance(first, libcst.SimpleString)
            and first.evaluated_value == LocatedProgram.BASH
        ):
            self.found.append((command, bool(self.scopes) and self.scopes[-1]))


# %% the fix


class LocatedBashFix(CodeFix[BashCommandLine]):
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
    def imports(cls) -> tuple[ImportedName, ...]:
        """
        The import of :class:`basstler.bash.Bash`.
        """
        return (ImportedName(Bash.__module__, Bash.__name__),)

    def replacement(self, specification: BashCommandLine) -> libcst.CSTNode:
        arguments = [
            libcst.Arg(
                value=element.value,
                star="*" if isinstance(element, libcst.StarredElement) else "",
                comma=element.comma,
            )
            for element in specification.node.elements[1:]
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
class BashByNameChecker(FixableChecker[BashCommandLine]):
    """
    Finds command lines whose program is bash given by its name, which Windows resolves
    to WSL's launcher: those passed to a :mod:`subprocess` function, and those returned.
    """

    @classproperty
    def fix(cls) -> CodeFix[BashCommandLine]:
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
    ) -> Iterator[BashCommandLine]:
        for command, location in self.command_lines(module, with_environment=True):
            yield BashCommandLine(location, command)

    @override
    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        """
        Also report the command lines with no environment in scope, which no fix covers.

        See :meth:`basstler.code_rules.fixes.FixableChecker.violations`.
        """
        yield from super().violations(path)
        module = PositionedModule(libcst.parse_module(path.read_text(encoding="utf-8")))
        for _, location in self.command_lines(module, with_environment=False):
            yield CodeRuleViolation(
                path,
                location.start.line,
                location.end.line,
                f"{self.violation_description}; no `{ScopedName.ENVIRONMENT}` is in "
                f"scope, so `{CodeRulesCommand.FIX.invocation}` leaves it",
            )

    @staticmethod
    def command_lines(
        module: PositionedModule, with_environment: bool
    ) -> Iterator[tuple[libcst.List | libcst.Tuple, CodeRange]]:
        """
        :param with_environment: Whether to find the command lines in a function with
            an environment parameter, or those with none.
        :return: The command lines of *module* starting with the name of bash, with
            their code ranges.
        """
        finder = CommandLineFinder()
        module.module.visit(finder)
        for command, has_environment in finder.found:
            if has_environment == with_environment:
                yield command, module.positions[command]
