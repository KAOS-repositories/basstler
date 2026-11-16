"""
The type checkers the experiment installs from PyPI, each into a virtual environment of
its own.
"""

from __future__ import annotations

import json
import os
import re
from abc import ABC
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from basstler.command_run import CommandRun
from basstler.experiments.receiver_inference.checker_reports import (
    MypyDiagnostic,
    PyrightReport,
)
from basstler.experiments.tool_installation import ToolInstallation
from basstler.review_triage.commit_tree import PACKAGE_INITIALIZER, CommitModules
from basstler.review_triage.type_checkers import (
    JSON_OBJECT_START,
    Pyrefly,
    RevealedType,
    SourcePosition,
    TypeChecker,
)

MYPY_REVEALED_TYPE = re.compile(r'Revealed type is "(.*)"')
"""
Mypy's note on a revealed type, the type its group.
"""

PYRIGHT_REVEALED_TYPE = re.compile(r'Type of ".*" is "(.*)"')
"""
Pyright's note on a revealed type, the type its group.
"""

PYRIGHT_CONFIGURATION = "pyrightconfig.json"
"""
The file pyright reads its configuration from.
"""


@dataclass(frozen=True)
class InstalledTypeChecker(TypeChecker, ABC):
    """
    A type checker installed from PyPI into a virtual environment of its own.
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


@dataclass(frozen=True)
class Mypy(InstalledTypeChecker):
    """
    Mypy, writing one JSON object per diagnostic.
    """

    @property
    def program(self) -> tuple[str, ...]:
        return (str(self.installation.python), "-m", "mypy")

    def command(
        self, files: list[str], search_paths: list[Path], workspace: Path
    ) -> list[str]:
        return [
            *self.program,
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

    def checks(self, path: str, modules: CommitModules) -> bool:
        """
        :meth:`TypeChecker.checks`: not a file under a directory holding an
        ``__init__.py`` whose name is no identifier, which mypy refuses to check
        anything beside.
        """
        return all(
            directory.name.isidentifier()
            for directory in PurePosixPath(path).parents
            if modules.tree.holds(directory / PACKAGE_INITIALIZER)
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
class Pyright(InstalledTypeChecker):
    """
    Pyright, writing one JSON report, configured by a file naming the search paths; it
    resolves the files a configuration includes against the configuration's directory,
    so they are given on its command line instead.
    """

    @property
    def program(self) -> tuple[str, ...]:
        return (str(self.installation.python), "-m", "pyright")

    def command(
        self, files: list[str], search_paths: list[Path], workspace: Path
    ) -> list[str]:
        configuration = workspace / PYRIGHT_CONFIGURATION
        configuration.write_text(
            json.dumps({"extraPaths": list(map(str, search_paths))}),
            encoding="utf-8",
        )
        return [
            *self.program,
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
class InstalledPyrefly(InstalledTypeChecker, Pyrefly):
    """
    :class:`Pyrefly` as the triage runs it, its latest release installed apart.
    """

    @property
    def program(self) -> tuple[str, ...]:
        """
        :meth:`Pyrefly.program`, the program of its own installation.
        """
        return (str(self.installation.program("pyrefly")),)
