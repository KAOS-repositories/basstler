"""
Static type checkers asked for the type of expressions: each expression is wrapped in
``reveal_type(...)``, which every checker answers with a note at the argument's
position.
"""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path, PurePath

from basstler.experiments.receiver_inference.checker_reports import (
    MypyDiagnostic,
    PyreflyReport,
    PyrightReport,
)
from basstler.experiments.tool_installation import CommandRun, ToolInstallation
from basstler.review_triage.commit_tree import PACKAGE_INITIALIZER

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

MYPY_REVEALED_TYPE = re.compile(r'Revealed type is "(.*)"')
"""
Mypy's note on a revealed type, the type its group.
"""

PYRIGHT_REVEALED_TYPE = re.compile(r'Type of ".*" is "(.*)"')
"""
Pyright's note on a revealed type, the type its group.
"""

PYREFLY_REVEALED_TYPE = "reveal-type"
"""
The kind of Pyrefly's entry on a revealed type.
"""

PYREFLY_REVEALED_PREFIX = "revealed type: "
"""
What Pyrefly writes before a revealed type.
"""

PYRIGHT_CONFIGURATION = "pyrightconfig.json"
"""
The file pyright reads its configuration from.
"""

PYREFLY_PRESET = "default"
"""
Pyrefly's preset of checks for a project it has no configuration for; its fallback,
``basic``, leaves out the revealed types of some files.
"""

JSON_OBJECT_START = "{"
"""
Where a JSON report starts after any warning a checker writes before it.
"""

CHECKED_EXIT_STATUSES = frozenset({0, 1})
"""
The exit statuses of a checker that checked the files, finding errors or none.
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


# %% the checkers


@dataclass(frozen=True)
class TypeChecker(ABC):
    """
    A static type checker installed from PyPI, run over some files of a checkout.
    """

    installation: ToolInstallation
    """
    Where the checker is installed.
    """

    @property
    def name(self) -> str:
        """
        The checker's distribution name, naming it in results.
        """
        return self.installation.distribution

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

    def checks(self, path: str, checkout: Path) -> bool:
        """
        :param path: A file relative to the checkout.
        :param checkout: The checkout.
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
        :raises ExperimentCommandFailed: If the checker failed to check them.
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
        :param reported: A file's path as a checker reports it.
        :param checkout: The directory the checker ran in.
        :return: The path relative to the checkout, with forward slashes.
        """
        path = Path(reported)
        if path.is_absolute():
            path = path.resolve().relative_to(checkout.resolve())
        return PurePath(path).as_posix()


@dataclass(frozen=True)
class Mypy(TypeChecker):
    """
    Mypy, writing one JSON object per diagnostic.
    """

    def command(
        self, files: list[str], search_paths: list[Path], workspace: Path
    ) -> list[str]:
        return [
            str(self.installation.python),
            "-m",
            "mypy",
            "--output",
            "json",
            "--show-column-numbers",
            "--no-error-summary",
            "--follow-imports",
            "silent",
            "--ignore-missing-imports",
            "--explicit-package-bases",
            "--cache-dir",
            str(workspace / "cache"),
            *files,
        ]

    def checks(self, path: str, checkout: Path) -> bool:
        """
        :meth:`TypeChecker.checks`: not a file under a directory holding an
        ``__init__.py`` whose name is no identifier, which mypy refuses to check
        anything beside.
        """
        return all(
            directory.name.isidentifier()
            for directory in Path(path).parents
            if (checkout / directory / PACKAGE_INITIALIZER).is_file()
        )

    def environment(self, search_paths: list[Path]) -> dict[str, str]:
        """
        :meth:`TypeChecker.environment`, with the search paths as ``MYPYPATH``.
        """
        return dict(os.environ) | {"MYPYPATH": os.pathsep.join(map(str, search_paths))}

    def revealed_types(self, run: CommandRun, checkout: Path) -> list[RevealedType]:
        diagnostics = [
            MypyDiagnostic.from_json(json.loads(line))
            for line in run.output.splitlines()
            if line.strip()
        ]
        return [
            RevealedType(
                SourcePosition(
                    self.relative_path(diagnostic.file, checkout),
                    diagnostic.line,
                    diagnostic.column,
                ),
                revealed.group(1),
            )
            for diagnostic in diagnostics
            if (revealed := MYPY_REVEALED_TYPE.fullmatch(diagnostic.message))
        ]


@dataclass(frozen=True)
class Pyright(TypeChecker):
    """
    Pyright, writing one JSON report, configured by a file naming the search paths; it
    resolves the files a configuration includes against the configuration's directory,
    so they are given on its command line instead.
    """

    def command(
        self, files: list[str], search_paths: list[Path], workspace: Path
    ) -> list[str]:
        configuration = workspace / PYRIGHT_CONFIGURATION
        configuration.write_text(
            json.dumps({"extraPaths": list(map(str, search_paths))}),
            encoding="utf-8",
        )
        return [
            str(self.installation.python),
            "-m",
            "pyright",
            "--outputjson",
            "--pythonpath",
            str(self.installation.python),
            "--project",
            str(configuration),
            *files,
        ]

    def environment(self, search_paths: list[Path]) -> dict[str, str]:
        """
        :meth:`TypeChecker.environment`, keeping the language server pyright downloads
        on its first run inside its installation.
        """
        return dict(os.environ) | {
            "PYRIGHT_PYTHON_CACHE_DIR": str(self.installation.downloads[0])
        }

    def revealed_types(self, run: CommandRun, checkout: Path) -> list[RevealedType]:
        report = PyrightReport.from_json(
            json.loads(run.output[run.output.index(JSON_OBJECT_START) :])
        )
        return [
            RevealedType(
                SourcePosition(
                    self.relative_path(diagnostic.file, checkout),
                    diagnostic.range.start.line + 1,
                    diagnostic.range.start.character,
                ),
                revealed.group(1),
            )
            for diagnostic in report.diagnostics
            if (revealed := PYRIGHT_REVEALED_TYPE.fullmatch(diagnostic.message))
        ]


@dataclass(frozen=True)
class Pyrefly(TypeChecker):
    """
    Pyrefly, writing one JSON report of its errors, revealed types among them.
    """

    def command(
        self, files: list[str], search_paths: list[Path], workspace: Path
    ) -> list[str]:
        return [
            str(self.installation.program("pyrefly")),
            "check",
            "--preset",
            PYREFLY_PRESET,
            "--output-format",
            "json",
            *(
                argument
                for path in search_paths
                for argument in ("--search-path", str(path))
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
