"""
Finds commands that start bash by its name instead of through
:class:`basstler.bash.Bash`, and fixes them.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from types import ModuleType
from typing import override

import libcst
from libcst import matchers

from basstler.bash import Bash, LocatedProgram
from basstler.class_property import classproperty
from basstler.code_modification.patterns import CodePattern
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.specification import Specification
from basstler.code_modification.syntax import ExpressionSyntax
from basstler.code_rules.fixes import (
    BehaviourDeclaration,
    BehaviourEffect,
    CodeFix,
    FixableChecker,
)
from basstler.code_rules.subprocess_function import SubprocessFunction

# %% the patterns


class BashEnvironment(StrEnum):
    """
    The environment the fix locates bash in, as the code naming it.
    """

    ENVIRONMENT_PARAMETER = "environment"
    """
    The parameter of the function around the command line, where it has one.
    """

    PROCESS_ENVIRONMENT = "os.environ"
    """
    The environment of the process, where the function has no environment parameter.
    """

    @property
    def expression(self) -> libcst.BaseExpression:
        """
        The code naming the environment.
        """
        return libcst.parse_expression(self.value)

    @property
    def required_modules(self) -> tuple[ModuleType, ...]:
        """
        The modules the code naming the environment needs imported.
        """
        if self is BashEnvironment.PROCESS_ENVIRONMENT:
            return (os,)
        return ()


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
class StartedCommandLine(Specification):
    """
    A command line starting bash by its name, and the environment to locate bash in.
    """

    node: libcst.List | libcst.Tuple
    """
    The command line.
    """

    environment: BashEnvironment
    """
    The environment the fix locates bash in.
    """


@dataclass
class CommandLineFinder(libcst.CSTVisitor):
    """
    Collects the command lines a module starts bash by its name with.
    """

    module: PositionedModule
    """
    The module visited.
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
                parameter.name.value == BashEnvironment.ENVIRONMENT_PARAMETER
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
        captures = BashStarted.captures(node, self.module.metadata)
        if captures is None:
            return
        command = libcst.ensure_type(
            captures[BashStarted.saved_command_name], libcst.List | libcst.Tuple
        )
        self.found.append(
            StartedCommandLine(
                self.module.positions[command],
                command,
                BashEnvironment.ENVIRONMENT_PARAMETER
                if self.scopes and self.scopes[-1]
                else BashEnvironment.PROCESS_ENVIRONMENT,
            )
        )


# %% the fix


class LocatedBashFix(CodeFix[StartedCommandLine]):
    """
    Builds the command line with the bash :class:`basstler.bash.Bash` locates in the
    environment, as a tuple where it was one.
    """

    @classproperty
    def behaviour(cls) -> BehaviourDeclaration:
        return BehaviourDeclaration(
            BehaviourEffect.CHANGED,
            "The command starts the bash located in the environment, never WSL's "
            "launcher; nothing changes where the bash found by name is the located "
            "one.",
        )

    def required_imports(
        self, specification: StartedCommandLine
    ) -> tuple[type | ModuleType, ...]:
        return (*specification.environment.required_modules, Bash)

    def replacement(self, specification: StartedCommandLine) -> libcst.Call:
        command = specification.node
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
            args=[libcst.Arg(specification.environment.expression)],
        )
        command_line = libcst.Call(
            func=libcst.Attribute(
                value=locate, attr=libcst.Name(Bash.command.__name__)
            ),
            args=arguments,
        )
        if isinstance(command, libcst.List):
            return command_line
        return libcst.Call(
            func=libcst.Name(tuple.__name__), args=[libcst.Arg(command_line)]
        )


# %% the check


@dataclass(frozen=True)
class BashByNameChecker(FixableChecker[StartedCommandLine]):
    """
    Finds command lines whose program is bash given by its name, which Windows resolves
    to WSL's launcher: those passed to a :mod:`subprocess` function, and those returned.
    """

    @classproperty
    def fix(cls) -> CodeFix[StartedCommandLine]:
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
    ) -> Iterator[StartedCommandLine]:
        finder = CommandLineFinder(module)
        module.module.visit(finder)
        yield from finder.found
