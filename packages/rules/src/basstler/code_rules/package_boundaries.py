"""
Finds imports that cross from one distribution into another it does not list, or into a
third-party library it does not require.
"""

from __future__ import annotations

import importlib.metadata
import re
import sys
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from types import TracebackType

import libcst
from libcst.helpers import get_full_name_for_node

from basstler.code_modification.patterns import Occurrence
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.source_file import PythonSourceFile
from basstler.code_rules.checker import CodeRuleChecker, CodeRuleViolation
from basstler.directory_tree import DirectoryTree
from basstler.git.commands import GitCommandRunner
from basstler.locations import PackageLocation, WorkspaceLocation
from basstler.module import Module
from basstler.package_map import REQUIREMENT_NAME, Workspace

# %% imports


@dataclass(frozen=True, order=True)
class HasImportedModule:
    """
    Something that names a module of a distribution another module imports.
    """

    imported_module: Module
    """
    The module imported, relative to ``basstler``.
    """


@dataclass(frozen=True)
class ImportStatement(Occurrence):
    """
    An absolute import statement, for one imported module.
    """

    module: Module
    """
    The module imported, or read from, as the statement spells it.
    """

    names: tuple[str, ...]
    """
    The names a ``from`` import takes from :attr:`module`; none for a plain import.
    """


@dataclass(frozen=True)
class ModuleImport(HasImportedModule):
    """
    One module of the package that an import statement imports.
    """

    statement: ImportStatement
    """
    The statement importing it.
    """


@dataclass(frozen=True, order=True)
class ImportCrossing(ABC):
    """
    A module importing something its own distribution may not.
    """

    importing_module: Module
    """
    The module holding the import, relative to ``basstler``.
    """

    @abstractmethod
    def new_import_message(self) -> str:
        """
        :return: The error reporting that the module newly holds this import.
        """


@dataclass(frozen=True, order=True)
class BoundaryCrossing(HasImportedModule, ImportCrossing):
    """
    A module importing a module of a distribution its own distribution does not list.
    """

    def new_import_message(self) -> str:
        return (
            f"basstler.{self.importing_module} newly imports "
            f"basstler.{self.imported_module} across a distribution boundary; "
            "move the code or the import"
        )


@dataclass(frozen=True, order=True)
class LibraryCrossing(ImportCrossing):
    """
    A module importing a third-party library its own distribution does not require.
    """

    imported_library: Module
    """
    The top-level package imported.
    """

    def new_import_message(self) -> str:
        return (
            f"basstler.{self.importing_module} newly imports the library "
            f"{self.imported_library}, which its distribution does not require; "
            "require it in the distribution's pyproject.toml or move the import"
        )


@dataclass(frozen=True)
class ModuleRenames:
    """
    The modules of the package a change moved.
    """

    new_module_by_old_module: Mapping[Module, Module]
    """
    Each moved module, relative to ``basstler``, as it was before the change and as it
    is after.
    """

    def current_module(self, module: Module) -> Module:
        """
        :param module: A module as it was before the change.
        :return: It as it is after the change; *module* itself when it did not move.
        """
        return self.new_module_by_old_module.get(module, module)


@dataclass(frozen=True)
class PackageCrossings:
    """
    Every boundary crossing of one checkout of the package.
    """

    crossings: tuple[BoundaryCrossing, ...]
    """
    The crossings of distributions, each once, ordered by importing and then imported
    module.
    """

    library_crossings: tuple[LibraryCrossing, ...] = ()
    """
    The crossings of libraries, each once, ordered by importing module and then library.
    """

    @property
    def all_crossings(self) -> tuple[ImportCrossing, ...]:
        """
        The crossings of distributions, then those of libraries.
        """
        return (*self.crossings, *self.library_crossings)

    def added_since(self, base: PackageCrossings) -> tuple[ImportCrossing, ...]:
        """
        :param base: The crossings of the checkout this one is compared with.
        :return: The crossings this checkout has and *base* does not.
        """
        return tuple(
            crossing
            for crossing in self.all_crossings
            if crossing not in base.all_crossings
        )

    def renamed(self, renames: ModuleRenames) -> PackageCrossings:
        """
        :param renames: The modules a change moved.
        :return: These crossings, with each module named as it is after the change.
        """
        return PackageCrossings(
            crossings=tuple(
                BoundaryCrossing(
                    importing_module=renames.current_module(crossing.importing_module),
                    imported_module=renames.current_module(crossing.imported_module),
                )
                for crossing in self.crossings
            ),
            library_crossings=tuple(
                LibraryCrossing(
                    importing_module=renames.current_module(crossing.importing_module),
                    imported_library=crossing.imported_library,
                )
                for crossing in self.library_crossings
            ),
        )


# %% installed libraries

EXTRA_MARKER = re.compile(r"\bextra\s*==")
"""
The environment marker of a requirement that only an extra brings in.
"""


@dataclass(frozen=True)
class InstalledLibraries:
    """
    The distributions installed in the running environment and what each requires.
    """

    @staticmethod
    def canonical_distribution_name(name: str) -> str:
        """
        :param name: A distribution's name as any requirement or metadata spells it.
        :return: The name with runs of ``-``, ``_`` and ``.`` read as one ``-``, in lower
            case.
        """
        return re.sub(r"[-_.]+", "-", name).lower()

    @cached_property
    def distributions_by_package(self) -> Mapping[str, frozenset[str]]:
        """
        The names of the distributions providing each top-level importable package.
        """
        return {
            package: frozenset(map(self.canonical_distribution_name, names))
            for package, names in importlib.metadata.packages_distributions().items()
        }

    @cached_property
    def requirements_by_distribution(self) -> Mapping[str, frozenset[str]]:
        """
        The names of the distributions each installed distribution requires, without
        those only an extra requires.
        """
        return {
            self.canonical_distribution_name(distribution.metadata["Name"]): frozenset(
                self.canonical_distribution_name(
                    REQUIREMENT_NAME.match(requirement).group()
                )
                for requirement in distribution.requires or ()
                if not EXTRA_MARKER.search(requirement)
            )
            for distribution in importlib.metadata.distributions()
        }

    def distributions_providing_package(self, package: Module) -> frozenset[str]:
        """
        :param package: A top-level importable package.
        :return: The distributions providing it; none when it is installed nowhere.
        """
        return self.distributions_by_package.get(str(package), frozenset())

    def resolve_required_distributions(self, names: Iterable[str]) -> frozenset[str]:
        """
        :param names: Names of distributions, as a ``pyproject.toml`` spells them.
        :return: Them and every distribution they require in turn, each canonically
            named.
        """
        closure: set[str] = set()
        pending = [self.canonical_distribution_name(name) for name in names]
        while pending:
            name = pending.pop()
            if name in closure:
                continue
            closure.add(name)
            pending.extend(self.requirements_by_distribution.get(name, ()))
        return frozenset(closure)


# %% the checker


@dataclass(frozen=True)
class PackageBoundaryChecker(CodeRuleChecker):
    """
    Reports an import of a distribution the importing module's distribution does not
    list.
    """

    workspace: Workspace = field(
        default_factory=lambda: Workspace(PackageLocation.SOURCE_TREE.value)
    )
    """
    The distributions checked; files outside their parts of ``basstler`` are not.
    """

    installed_libraries: InstalledLibraries = field(default_factory=InstalledLibraries)
    """
    The libraries installed, which the imported ones are mapped to.
    """

    @cached_property
    def namespace_root(self) -> Module:
        """
        The package every distribution's modules lie in.
        """
        return Module.from_dotted_name(PackageLocation.DIRECTORY.name)

    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        module = self.module_of_file(path)
        if module is None:
            return
        importing = self.workspace.package_map.claiming(str(module))
        for crossing in self.crossings(path):
            imported = self.workspace.package_map.claiming(
                str(crossing.imported_module)
            )
            yield CodeRuleViolation(
                path,
                crossing.statement.location.start.line,
                crossing.statement.location.end.line,
                f"{importing.distribution} imports basstler.{crossing.imported_module} "
                f"from {imported.distribution}, which its pyproject.toml does not list; "
                "move the code or the import",
            )
        for statement in self.library_crossings(path):
            yield CodeRuleViolation(
                path,
                statement.location.start.line,
                statement.location.end.line,
                f"{importing.distribution} imports {statement.module.top_level_package}"
                ", which neither its pyproject.toml nor a distribution it lists "
                "requires; require it there or move the import",
            )

    def package_crossings(self) -> PackageCrossings:
        """
        :return: The crossings of every module of :attr:`workspace`.
        """
        paths = {
            path: module
            for directory in self.workspace.namespace_package.directories
            for path in directory.rglob("*.py")
            if (module := self.module_of_file(path)) is not None
        }
        return PackageCrossings(
            crossings=tuple(
                sorted(
                    {
                        BoundaryCrossing(module, crossing.imported_module)
                        for path, module in paths.items()
                        for crossing in self.crossings(path)
                    }
                )
            ),
            library_crossings=tuple(
                sorted(
                    {
                        LibraryCrossing(module, crossing.module.top_level_package)
                        for path, module in paths.items()
                        for crossing in self.library_crossings(path)
                    }
                )
            ),
        )

    def module_renames(self, git: GitCommandRunner, base_commit: str) -> ModuleRenames:
        """
        :param git: The checkout of the package.
        :param base_commit: The commit the checked out package is compared with.
        :return: The modules of :attr:`workspace` git detects as moved since
            *base_commit*.
        """
        listing = git.run(
            "diff",
            "--name-status",
            "--find-renames",
            "--diff-filter=R",
            "--relative",
            base_commit,
            "HEAD",
            "--",
            str(self.workspace.root / WorkspaceLocation.PACKAGES),
        )
        new_module_by_old_module = {}
        for line in listing.splitlines():
            _, old_path, new_path = line.split("\t")
            old_module = self.module_of_file(git.working_directory / old_path)
            new_module = self.module_of_file(git.working_directory / new_path)
            if old_path.endswith(".py") and old_module and new_module:
                new_module_by_old_module[old_module] = new_module
        return ModuleRenames(new_module_by_old_module)

    def module_of_file(self, path: Path) -> Module | None:
        """
        :param path: A Python source file.
        :return: The module it holds, relative to ``basstler``; none for a file outside
            every distribution's part of it.
        """
        source = path.resolve()
        directory = next(
            (
                directory.resolve()
                for directory in self.workspace.namespace_package.directories
                if source.is_relative_to(directory.resolve())
            ),
            None,
        )
        if directory is None:
            return None
        parts = source.relative_to(directory).with_suffix("").parts
        return Module(parts[:-1] if parts[-1] == "__init__" else parts)

    def crossings(self, path: Path) -> Iterator[ModuleImport]:
        """
        :param path: A source file of a module some distribution claims.
        :return: Every import in it of a module of a distribution the module's own
            distribution does not list.
        """
        importing = self.workspace.package_map.claiming(str(self.module_of_file(path)))
        allowed = {importing.distribution, *importing.dependencies}
        for module_import in self.module_imports(path):
            imported = self.workspace.package_map.claiming(
                str(module_import.imported_module)
            )
            if imported is None or imported.distribution in allowed:
                continue
            yield module_import

    def library_crossings(self, path: Path) -> Iterator[ImportStatement]:
        """
        :param path: A source file of a module some distribution claims.
        :return: Every import in it of a library neither its own distribution nor a
            distribution it lists requires, directly or through what they require.
        """
        importing = self.workspace.package_map.claiming(str(self.module_of_file(path)))
        allowed = self.installed_libraries.resolve_required_distributions(
            self.workspace.package_map.libraries_required_by_distribution(
                importing.distribution
            )
        )
        for statement in self.library_imports(path):
            providers = self.installed_libraries.distributions_providing_package(
                statement.module.top_level_package
            )
            if not providers & allowed:
                yield statement

    def library_imports(self, path: Path) -> Iterator[ImportStatement]:
        """
        :param path: A Python source file.
        :return: Every import in it of a package that is neither the standard library
            nor ``basstler``.
        """
        for statement in self.import_statements(path):
            package = statement.module.top_level_package
            if package != self.namespace_root and str(package) not in (
                sys.stdlib_module_names
            ):
                yield statement

    def module_imports(self, path: Path) -> Iterator[ModuleImport]:
        """
        :param path: A Python source file.
        :return: Every import in it of a module of the package.
        """
        for statement in self.import_statements(path):
            if not statement.module.is_within(self.namespace_root):
                continue
            package = statement.module.relative_to(self.namespace_root)
            if not statement.names and package.parts:
                yield ModuleImport(package, statement)
            for name in statement.names:
                yield ModuleImport(
                    self.resolve_imported_module(package, name), statement
                )

    def import_statements(self, path: Path) -> Iterator[ImportStatement]:
        """
        :param path: A Python source file.
        :return: Each of its absolute imports, one per imported module.
        """
        module = PositionedModule(PythonSourceFile(path).parse())
        for statement, location in module.positions.items():
            if isinstance(statement, libcst.Import):
                for alias in statement.names:
                    yield ImportStatement(
                        statement, location, self.spelled_module(alias.name), ()
                    )
            if isinstance(statement, libcst.ImportFrom) and not statement.relative:
                names = (
                    ["*"]
                    if isinstance(statement.names, libcst.ImportStar)
                    else [
                        str(self.spelled_module(alias.name))
                        for alias in statement.names
                    ]
                )
                yield ImportStatement(
                    statement,
                    location,
                    self.spelled_module(statement.module),
                    tuple(names),
                )

    @staticmethod
    def spelled_module(name: libcst.Attribute | libcst.Name | None) -> Module:
        """
        :return: The module *name* spells; the module without parts where there is none.
        """
        return Module.from_dotted_name(
            get_full_name_for_node(name) or "" if name is not None else ""
        )

    def resolve_imported_module(self, package: Module, name: str) -> Module:
        """
        :param package: The module, relative to ``basstler``, a ``from`` import reads
            from.
        :param name: A name it imports.
        :return: The module *name* is, when it is one, else *package*.
        """
        candidate = Module((*package.parts, name))
        location = Path(*candidate.parts)
        namespace_package = self.workspace.namespace_package
        if namespace_package.every(location) or namespace_package.every(
            location.with_suffix(".py")
        ):
            return candidate
        return package


# %% the package at another commit


@dataclass
class PackageAtCommit:
    """
    The workspace as one commit holds it, in a detached worktree removed on exit.
    """

    git: GitCommandRunner
    """
    The checkout the worktree is added to.
    """

    commit: str
    """
    The commit checked out.
    """

    workspace_root: Path
    """
    The workspace's root in :attr:`git`'s checkout.
    """

    directory: Path = field(init=False)
    """
    The worktree's root, once entered.
    """

    def __enter__(self) -> PackageBoundaryChecker | None:
        """
        :return: A checker of the workspace at :attr:`commit`, under the package map
            its distributions declare there; none when it holds no distributions.
        """
        self.directory = Path(tempfile.mkdtemp())
        self.git.run(
            "worktree", "add", "--detach", "--quiet", str(self.directory), self.commit
        )
        workspace = Workspace(
            self.directory
            / self.workspace_root.resolve().relative_to(
                self.git.working_directory.resolve()
            )
        )
        if not workspace.package_directories:
            return None
        return PackageBoundaryChecker(workspace)

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Remove the worktree, whether or not the workspace was read.
        """
        self.git.attempt("worktree", "remove", "--force", str(self.directory))
        DirectoryTree(self.directory).remove()
