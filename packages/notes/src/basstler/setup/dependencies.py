#!/usr/bin/env python3
"""
What this package needs installed, and which of it this environment is missing: read
from the checkout's declarations, else from the installed distributions' metadata.

Usage:
    "${BASSTLER_PYTHON}" -m basstler.setup.dependencies [--declaration <pyproject.toml>]

..note:: Imports nothing outside the standard library, since it runs before any
    install.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from importlib.metadata import distributions
from pathlib import Path
from typing import Any

from basstler.class_property import classproperty
from basstler.exit_codes import CommandFailure, ExitCode
from basstler.locations import PackageLocation, WorkspaceLocation
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its command prints through.
"""


class PyprojectKey(StrEnum):
    """
    The keys of ``pyproject.toml`` this module reads.
    """

    PROJECT = "project"
    """
    The table a package's own metadata lives in.
    """

    NAME = "name"
    """
    The field of that table naming the package's own distribution.
    """

    DEPENDENCIES = "dependencies"
    """
    The field of that table, and of the sibling-pins hook's, listing the requirement
    specifiers.
    """

    TOOL = "tool"
    """
    The table every tool's settings sit under.
    """

    HATCH = "hatch"
    """
    The build backend's table.
    """

    METADATA = "metadata"
    """
    The backend's table of how the metadata is built.
    """

    HOOKS = "hooks"
    """
    The table of the hooks filling in the metadata's dynamic fields.
    """

    SIBLING_PINS = "basstler-sibling-pins"
    """
    The hook holding a distribution's requirements, its basstler ones unpinned.
    """


class RequirementMarker(StrEnum):
    """
    The environment-marker fragments of an installed distribution's requirements this
    module reads.
    """

    EXTRA = "extra =="
    """
    Marks a requirement that applies only when one of the distribution's extras is
    requested, which a plain install does not.
    """


class DependencyExitCode(ExitCode):
    """
    How the command ended, as its caller reads it.
    """

    SUCCESS = 0
    """
    The missing requirements, if any, were printed.
    """

    UNREADABLE_DECLARATION = 1
    """
    The declaration could not be read, so nothing was printed.
    """


@dataclass
class UnreadableDependencyDeclarationError(CommandFailure):
    """
    Raised when the declaration cannot be read, so nothing can be said about what is
    missing.

    Distinct from *nothing is missing*, which is what a caller would otherwise conclude
    from an empty answer and act on by installing nothing.
    """

    @classproperty
    def exit_code(cls) -> DependencyExitCode:
        """:return: The status this kind of error ends a command with."""
        return DependencyExitCode.UNREADABLE_DECLARATION

    declaration: Path
    """
    The file that was to be read.
    """

    def __str__(self) -> str:
        """:return: What to tell a reader who asked what is missing and cannot be told."""
        return (
            f"{self.declaration} does not exist, so this package's dependencies cannot "
            f"be read"
        )


@dataclass
class MalformedDependencyDeclarationError(UnreadableDependencyDeclarationError):
    """
    Raised when the declaration exists but is not valid TOML.
    """

    def __str__(self) -> str:
        """:return: What to tell a reader who asked what is missing and cannot be told."""
        return (
            f"{self.declaration} is not valid TOML, so this package's dependencies "
            f"cannot be read"
        )


@dataclass(frozen=True)
class Dependency:
    """
    One requirement this package declares.
    """

    specifier: str
    """
    The requirement as ``pyproject.toml`` writes it, version bounds and all.
    """

    constraint_start: re.Pattern[str] = field(
        default=re.compile(r"[<>=!~;\[ ]"), repr=False, compare=False
    )
    """
    The first character that ends a distribution's name and begins a version bound, an extra
    or an environment marker, in a PEP 508 specifier.
    """

    @property
    def distribution_name(self) -> str:
        """:return: The distribution this requirement names, without its constraints."""
        return self.constraint_start.split(self.specifier, maxsplit=1)[0].strip()

    @property
    def is_basstler_distribution(self) -> bool:
        """
        :return: Whether this requirement names ``basstler`` or one of its
            ``basstler-`` distributions.
        """
        family = PackageLocation.DIRECTORY.value.name
        name = self.distribution_name.lower()
        return name == family or name.startswith(f"{family}-")

    @property
    def is_missing(self) -> bool:
        """
        Presence rather than version: an installed distribution is left alone, which is
        what lets a session start run this on every start and install nothing. Names are
        compared as PEP 503 does, so a declaration need not match a distribution's own
        spelling.

        :return: Whether this environment has no distribution of that name.
        """
        return next(iter(distributions(name=self.distribution_name)), None) is None


class RequirementSource(ABC):
    """
    Somewhere a package's requirements are stated: the package itself, then its
    dependencies.
    """

    @abstractmethod
    def requirements(self) -> tuple[Dependency, ...]:
        """
        :return: Everything an environment needs to run the package: the package itself,
            then its dependencies.
        """

    def missing(self) -> tuple[Dependency, ...]:
        """
        :return: The requirements this environment does not have.
        """
        return tuple(
            requirement for requirement in self.requirements() if requirement.is_missing
        )

    @staticmethod
    def for_this_package() -> RequirementSource:
        """
        :return: The checkout's workspace where the package runs from one, else the
            installed ``basstler`` distribution.
        """
        if PackageLocation.META_PACKAGE_METADATA.value.is_file():
            return WorkspaceDeclaration(PackageLocation.SOURCE_TREE.value)
        return InstalledDistribution(PackageLocation.DIRECTORY.value.name)


@dataclass(frozen=True)
class InstalledDistribution(RequirementSource):
    """
    An installed distribution, and the dependencies its metadata states.
    """

    name: str
    """
    The distribution's name.
    """

    def requirements(self) -> tuple[Dependency, ...]:
        """
        :return: The distribution itself, then every requirement its metadata states
            without an extra, in the order stated, each basstler distribution among them
            followed by its own; only itself when it is not installed.
        """
        installed = next(iter(distributions(name=self.name)), None)
        if installed is None:
            return (Dependency(self.name),)
        found = [Dependency(self.name)]
        for specifier in installed.requires or []:
            if RequirementMarker.EXTRA in specifier:
                continue
            dependency = Dependency(specifier)
            stated = (
                InstalledDistribution(dependency.distribution_name).requirements()
                if dependency.is_basstler_distribution
                else (dependency,)
            )
            found.extend(
                requirement for requirement in stated if requirement not in found
            )
        return tuple(found)


@dataclass(frozen=True)
class DependencyDeclaration(RequirementSource):
    """
    A ``pyproject.toml`` and the dependencies it declares.
    """

    path: Path
    """
    The ``pyproject.toml`` to read.
    """

    def project(self) -> Dependency:
        """
        :return: The package's own distribution, as a requirement of an environment that
            runs it.
        :raises UnreadableDependencyDeclarationError: If the file is absent.
        """
        return Dependency(self._project_table()[PyprojectKey.NAME])

    def dependencies(self) -> tuple[Dependency, ...]:
        """
        :return: Every dependency it declares, in ``[project]`` and then in the
            sibling-pins hook, in the order it declares them.
        :raises UnreadableDependencyDeclarationError: If the file is absent.
        """
        document = self._document()
        hook = (
            document.get(PyprojectKey.TOOL, {})
            .get(PyprojectKey.HATCH, {})
            .get(PyprojectKey.METADATA, {})
            .get(PyprojectKey.HOOKS, {})
            .get(PyprojectKey.SIBLING_PINS, {})
        )
        return tuple(
            Dependency(specifier)
            for specifier in (
                *document[PyprojectKey.PROJECT].get(PyprojectKey.DEPENDENCIES, []),
                *hook.get(PyprojectKey.DEPENDENCIES, []),
            )
        )

    def requirements(self) -> tuple[Dependency, ...]:
        """
        :return: Everything an environment needs to run the package: the package itself,
            then its dependencies.
        :raises UnreadableDependencyDeclarationError: If the file is absent.
        """
        return (self.project(), *self.dependencies())

    def _project_table(self) -> dict[str, Any]:
        """
        :return: The ``[project]`` table, the package's own metadata.
        :raises UnreadableDependencyDeclarationError: If the file is absent.
        :raises MalformedDependencyDeclarationError: If the file is not valid TOML.
        """
        return self._document()[PyprojectKey.PROJECT]

    def _document(self) -> dict[str, Any]:
        """
        :return: The whole ``pyproject.toml``.
        :raises UnreadableDependencyDeclarationError: If the file is absent.
        :raises MalformedDependencyDeclarationError: If the file is not valid TOML.
        """
        if not self.path.is_file():
            raise UnreadableDependencyDeclarationError(self.path)
        try:
            return tomllib.loads(self.path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            raise MalformedDependencyDeclarationError(self.path) from error


@dataclass(frozen=True)
class WorkspaceDeclaration(RequirementSource):
    """
    A checkout's workspace, whose ``basstler`` distribution requires what its own
    ``pyproject.toml`` and those of the basstler distributions it lists declare.
    """

    root: Path
    """
    The workspace's root.
    """

    def requirements(self) -> tuple[Dependency, ...]:
        """
        :return: The ``basstler`` distribution, then each requirement its declaration
            lists, each workspace distribution among them followed by its own.
        :raises UnreadableDependencyDeclarationError: If a declaration is absent.
        """
        declarations = {
            declaration.project().specifier: declaration
            for declaration in (
                DependencyDeclaration(path)
                for path in sorted(
                    (self.root / WorkspaceLocation.PACKAGES).glob(
                        f"*/{WorkspaceLocation.METADATA}"
                    )
                )
            )
        }
        return self.reached(
            declarations, Dependency(PackageLocation.DIRECTORY.value.name), []
        )

    def reached(
        self,
        declarations: dict[str, DependencyDeclaration],
        requirement: Dependency,
        found: list[Dependency],
    ) -> tuple[Dependency, ...]:
        """
        :param declarations: Each workspace distribution's declaration, by its name.
        :param requirement: A requirement to add to *found*.
        :param found: The requirements reached so far, extended in place.
        :return: *found*, with *requirement* and, for a workspace distribution, what it
            declares in turn.
        """
        declaration = declarations.get(requirement.distribution_name)
        if declaration is None:
            if requirement not in found:
                found.append(requirement)
            return tuple(found)
        own = Dependency(requirement.distribution_name)
        if own in found:
            return tuple(found)
        found.append(own)
        for dependency in declaration.dependencies():
            self.reached(declarations, dependency, found)
        return tuple(found)


def main() -> DependencyExitCode:
    """
    Print one specifier per missing requirement, for a caller to report.

    :return: How the command ended.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--declaration",
        type=Path,
        help="A pyproject.toml to read the dependencies from, instead of this package's "
        "own requirements",
    )
    declaration_path = parser.parse_args().declaration
    try:
        if declaration_path is None:
            source = RequirementSource.for_this_package()
        elif declaration_path.is_file():
            source = DependencyDeclaration(declaration_path)
        else:
            raise UnreadableDependencyDeclarationError(declaration_path)
        missing = source.missing()
    except CommandFailure as error:
        logger.error(str(error))
        return error.exit_code
    for requirement in missing:
        logger.info(requirement.specifier)
    return DependencyExitCode.SUCCESS


if __name__ == "__main__":
    sys.exit(main())
