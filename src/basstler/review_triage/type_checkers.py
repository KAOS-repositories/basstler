"""
Static type checkers asked for the type of expressions: each expression is wrapped in
``reveal_type(...)``, which every checker answers with a note at the argument's
position.
"""

from __future__ import annotations

import json
import os
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePath, PureWindowsPath
from typing import Annotated

from pydantic import Field

from basstler.command_run import CommandRun
from basstler.json_model import ValidatedJSONModel
from basstler.review_triage.commit_tree import CommitModules

UNION_SEPARATOR = re.compile(r"\s*\|\s*")
"""
What separates the members of a union a checker writes.
"""

NONE_TYPE = "None"
"""
How every checker writes the type of ``None``.
"""

UNKNOWN_TYPES = frozenset({"Any", "Unknown", "Never", "NoReturn", "object"})
"""
The types every class is, or none is, which name no class.
"""

NOT_INSTANCE_PREFIXES = ("type[", "def ", "(", "Overload[", "Module(")
"""
How a checker begins the type of a class itself, a function or a module.
"""

LITERAL_TYPE = re.compile(r"(?:[\w.]+\.)?Literal\[(?P<values>.*)\]")
"""
A ``Literal`` type as a checker writes it, its values the group ``values``.
"""

LITERAL_VALUE_SEPARATOR = ","
"""
What separates the values of a ``Literal`` type.
"""

INFERRED_MARKER = "*"
"""
What pyright appends to a type it inferred rather than read from a declaration.
"""

JSON_OBJECT_START = "{"
"""
Where a JSON report starts after any warning a checker writes before it.
"""

CHECKED_EXIT_STATUSES = frozenset({0, 1})
"""
The exit statuses of a checker that checked the files, finding errors or none.
"""

PYREFLY_REVEALED_TYPE = "reveal-type"
"""
The kind of Pyrefly's entry on a revealed type.
"""

PYREFLY_REVEALED_PREFIX = "revealed type: "
"""
What Pyrefly writes before a revealed type.
"""

PYREFLY_PRESET = "default"
"""
Pyrefly's preset of checks for a project it has no configuration for; its fallback,
``basic``, leaves out the revealed types of some files.
"""

PYREFLY_OUTPUT_FORMAT = "json"
"""
The format Pyrefly writes its report in.
"""


class PyreflyArgument(StrEnum):
    """
    The arguments of ``pyrefly`` basstler runs it with.
    """

    CHECK = "check"
    """
    The command checking files.
    """

    PRESET = "--preset"
    """
    The option naming the preset of checks.
    """

    OUTPUT_FORMAT = "--output-format"
    """
    The option naming the report's format.
    """

    SEARCH_PATH = "--search-path"
    """
    The option naming one directory imports are resolved in.
    """

    SKIP_INTERPRETER_QUERY = "--skip-interpreter-query"
    """
    The flag keeping Pyrefly from asking a Python interpreter for its packages.
    """

    DISABLE_SEARCH_PATH_HEURISTICS = "--disable-search-path-heuristics"
    """
    The flag keeping Pyrefly's search path to the directories it is given.
    """


# %% a revealed type


@dataclass(frozen=True, order=True)
class SourcePosition:
    """
    Where an expression starts in a file of a checkout.
    """

    path: str
    """
    The file's path relative to the checkout, with forward slashes.
    """

    line: int
    """
    Its line, counted from one.
    """

    column: int
    """
    Its column in characters, counted from zero.
    """


@dataclass(frozen=True)
class RevealedType:
    """
    The type a checker found for one expression, as it writes it.
    """

    position: SourcePosition
    """
    Where the expression starts.
    """

    text: str
    """
    The type, such as ``pkg.module.Class | None``.
    """

    @property
    def instance_class(self) -> str | None:
        """
        The name of the one class the expression is an instance of, ``None`` aside;
        ``None`` for a union, a class itself, a callable or an unknown type.
        """
        members = [
            member
            for member in UNION_SEPARATOR.split(self.text.strip())
            if member != NONE_TYPE
        ]
        if len(members) != 1:
            return None
        member = members[0].removesuffix(INFERRED_MARKER)
        if member.startswith(NOT_INSTANCE_PREFIXES):
            return None
        literal = LITERAL_TYPE.fullmatch(member)
        name = (
            self.enumeration_of(literal["values"])
            if literal
            else member.split("[", 1)[0].rsplit(".", 1)[-1]
        )
        if name is None or name in UNKNOWN_TYPES or not name.isidentifier():
            return None
        return name

    @staticmethod
    def enumeration_of(values: str) -> str | None:
        """
        :param values: The values of a ``Literal`` type, such as ``Color.RED, Color.BLUE``.
        :return: The name of the one enumeration all of them are members of, ``None``
            when they are not all members of one.
        """
        enumerations = {
            tuple(value.strip().split(".")[-2:-1])
            for value in values.split(LITERAL_VALUE_SEPARATOR)
        }
        if len(enumerations) != 1:
            return None
        [enumeration] = enumerations
        return enumeration[0] if enumeration else None


# %% Pyrefly's report


class PyreflyError(ValidatedJSONModel):
    """
    One entry of Pyrefly's ``--output-format json`` report.
    """

    path: str
    """
    The file, relative to where Pyrefly ran.
    """

    line: int
    """
    The line, counted from one.
    """

    column: int
    """
    The column of the parenthesis before a revealed expression, counted from one, which
    is the expression's column counted from zero.
    """

    kind: Annotated[str, Field(alias="name")]
    """
    What the entry reports, ``reveal-type`` for a revealed type.
    """

    description: str
    """
    The entry's text, ``revealed type: ...`` for a revealed type.
    """


class PyreflyReport(ValidatedJSONModel):
    """
    Pyrefly's ``--output-format json`` report.
    """

    errors: tuple[PyreflyError, ...]
    """
    Every entry, revealed types among them.
    """


# %% the checkers


class TypeChecker(ABC):
    """
    A static type checker, run over some files of a checkout.
    """

    @property
    @abstractmethod
    def program(self) -> tuple[str, ...]:
        """
        The command starting the checker, before its arguments.
        """

    @abstractmethod
    def command(
        self, files: list[str], search_paths: list[Path], workspace: Path
    ) -> list[str]:
        """
        :param files: The files checked, relative to the checkout.
        :param search_paths: The directories imports are resolved in.
        :param workspace: An empty directory the checker may write its cache and
            configuration to.
        :return: The command checking them, run in the checkout.
        """

    def environment(self, search_paths: list[Path]) -> dict[str, str]:
        """
        :param search_paths: The directories imports are resolved in.
        :return: The environment the command runs with.
        """
        return dict(os.environ)

    def checks(self, path: str, modules: CommitModules) -> bool:
        """
        :param path: A file of the commit, relative to its root.
        :param modules: The commit's modules.
        :return: Whether the checker can check the file; one it cannot is left out,
            its receivers unanswered.
        """
        return True

    @abstractmethod
    def revealed_types(self, run: CommandRun, checkout: Path) -> list[RevealedType]:
        """
        :param run: The checker's run.
        :param checkout: The directory it ran in.
        :return: Every type it revealed.
        """

    def reveal(
        self,
        files: list[str],
        search_paths: list[Path],
        checkout: Path,
        workspace: Path,
    ) -> list[RevealedType]:
        """
        :param files: The files checked, relative to the checkout.
        :param search_paths: The directories imports are resolved in.
        :param checkout: The checkout holding them.
        :param workspace: An empty directory the checker may write to.
        :return: Every type the checker revealed in them.
        :raises CommandFailed: If the checker failed to check them.
        """
        run = CommandRun.of(
            self.command(files, search_paths, workspace),
            checkout,
            self.environment(search_paths),
        ).finished(CHECKED_EXIT_STATUSES)
        return self.revealed_types(run, checkout)

    @staticmethod
    def relative_path(reported: str, checkout: Path) -> str:
        """
        :param reported: A file's path as a checker reports it, with either separator.
        :param checkout: The directory the checker ran in.
        :return: The path relative to the checkout, with forward slashes.
        """
        path = Path(PureWindowsPath(reported).as_posix())
        if path.is_absolute():
            path = path.resolve().relative_to(checkout.resolve())
        return PurePath(path).as_posix()


@dataclass(frozen=True)
class Pyrefly(TypeChecker):
    """
    Pyrefly, installed with basstler and run without any configuration but the
    directories imports resolve in, so its answers depend on its version and the files
    alone.
    """

    @property
    def program(self) -> tuple[str, ...]:
        return (sys.executable, "-m", "pyrefly")

    def command(
        self, files: list[str], search_paths: list[Path], workspace: Path
    ) -> list[str]:
        return [
            *self.program,
            PyreflyArgument.CHECK,
            PyreflyArgument.PRESET,
            PYREFLY_PRESET,
            PyreflyArgument.OUTPUT_FORMAT,
            PYREFLY_OUTPUT_FORMAT,
            PyreflyArgument.SKIP_INTERPRETER_QUERY,
            PyreflyArgument.DISABLE_SEARCH_PATH_HEURISTICS,
            *(
                argument
                for path in search_paths
                for argument in (PyreflyArgument.SEARCH_PATH, str(path))
            ),
            *files,
        ]

    def revealed_types(self, run: CommandRun, checkout: Path) -> list[RevealedType]:
        report = PyreflyReport.from_json(
            json.loads(run.output[run.output.index(JSON_OBJECT_START) :])
        )
        return [
            RevealedType(
                SourcePosition(
                    self.relative_path(error.path, checkout), error.line, error.column
                ),
                error.description.removeprefix(PYREFLY_REVEALED_PREFIX),
            )
            for error in report.errors
            if error.kind == PYREFLY_REVEALED_TYPE
        ]
