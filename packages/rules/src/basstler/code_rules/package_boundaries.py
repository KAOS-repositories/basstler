"""
Finds imports that cross from one distribution into another it does not list.
"""

from __future__ import annotations

import ast
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType

from basstler.directory_tree import DirectoryTree
from basstler.code_rules.checker import CodeRuleChecker, CodeRuleViolation
from basstler.git.commands import GitCommandRunner
from basstler.locations import PackageLocation, WorkspaceLocation
from basstler.package_map import Workspace

# %% imports


@dataclass(frozen=True)
class ModuleImport:
    """
    One module of the package that an import statement imports, with the statement.
    """

    imported_module: str
    """
    The dotted name, within ``basstler``, of the module imported.
    """

    statement: ast.Import | ast.ImportFrom
    """
    The import statement.
    """


@dataclass(frozen=True)
class BoundaryCrossing:
    """
    A module importing a module of a distribution its own distribution does not list.
    """

    importing_module: str
    """
    The dotted name, within ``basstler``, of the module holding the import.
    """

    imported_module: str
    """
    The dotted name, within ``basstler``, of the module it imports.
    """


@dataclass(frozen=True)
class ModuleRenames:
    """
    The modules of the package a change moved.
    """

    new_name_by_old_name: Mapping[str, str]
    """
    Each moved module's dotted name within ``basstler`` before the change, and its name
    after.
    """

    def current_name(self, module: str) -> str:
        """
        :param module: A module's dotted name within ``basstler`` before the change.
        :return: Its name after the change; *module* itself when it did not move.
        """
        return self.new_name_by_old_name.get(module, module)


@dataclass(frozen=True)
class PackageCrossings:
    """
    Every boundary crossing of one checkout of the package.
    """

    crossings: tuple[BoundaryCrossing, ...]
    """
    The crossings, each once, ordered by importing and then imported module.
    """

    def added_since(self, base: PackageCrossings) -> tuple[BoundaryCrossing, ...]:
        """
        :param base: The crossings of the checkout this one is compared with.
        :return: The crossings this checkout has and *base* does not.
        """
        return tuple(
            crossing for crossing in self.crossings if crossing not in base.crossings
        )

    def renamed(self, renames: ModuleRenames) -> PackageCrossings:
        """
        :param renames: The modules a change moved.
        :return: These crossings, with each module named as it is after the change.
        """
        return PackageCrossings(
            crossings=tuple(
                BoundaryCrossing(
                    importing_module=renames.current_name(crossing.importing_module),
                    imported_module=renames.current_name(crossing.imported_module),
                )
                for crossing in self.crossings
            )
        )


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

    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        module = self.module_name(path)
        if not module:
            return
        importing = self.workspace.package_map.claiming(module)
        for crossing in self.crossings(path):
            imported = self.workspace.package_map.claiming(crossing.imported_module)
            yield CodeRuleViolation(
                path,
                crossing.statement.lineno,
                crossing.statement.end_lineno or crossing.statement.lineno,
                f"{importing.distribution} imports basstler.{crossing.imported_module} "
                f"from {imported.distribution}, which its pyproject.toml does not list; "
                "move the code or the import",
            )

    def package_crossings(self) -> PackageCrossings:
        """
        :return: The crossings of every module of :attr:`workspace`.
        """
        crossings = {
            BoundaryCrossing(
                importing_module=module, imported_module=crossing.imported_module
            )
            for directory in self.workspace.namespace_package.directories
            for path in directory.rglob("*.py")
            if (module := self.module_name(path))
            for crossing in self.crossings(path)
        }
        return PackageCrossings(
            crossings=tuple(
                sorted(
                    crossings,
                    key=lambda crossing: (
                        crossing.importing_module,
                        crossing.imported_module,
                    ),
                )
            )
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
        new_name_by_old_name = {}
        for line in listing.splitlines():
            _, old_path, new_path = line.split("\t")
            old_module = self.module_name(git.working_directory / old_path)
            new_module = self.module_name(git.working_directory / new_path)
            if old_path.endswith(".py") and old_module and new_module:
                new_name_by_old_name[old_module] = new_module
        return ModuleRenames(new_name_by_old_name)

    def module_name(self, path: Path) -> str | None:
        """
        :param path: A Python source file.
        :return: Its dotted name within ``basstler``; none for a file outside every
            distribution's part of it.
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
        return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)

    def crossings(self, path: Path) -> Iterator[ModuleImport]:
        """
        :param path: A source file of a module some distribution claims.
        :return: Every import in it of a module of a distribution the module's own
            distribution does not list.
        """
        importing = self.workspace.package_map.claiming(self.module_name(path))
        allowed = {importing.distribution, *importing.dependencies}
        for module_import in self.module_imports(path):
            imported = self.workspace.package_map.claiming(
                module_import.imported_module
            )
            if imported is None or imported.distribution in allowed:
                continue
            yield module_import

    def module_imports(self, path: Path) -> Iterator[ModuleImport]:
        """
        :param path: A Python source file.
        :return: Every import in it of a module of the package.
        """
        for statement in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(statement, ast.Import):
                for alias in statement.names:
                    root, _, module = alias.name.partition(".")
                    if root == PackageLocation.DIRECTORY.name and module:
                        yield ModuleImport(module, statement)
            if isinstance(statement, ast.ImportFrom) and statement.level == 0:
                root, _, package = (statement.module or "").partition(".")
                if root == PackageLocation.DIRECTORY.name:
                    for alias in statement.names:
                        yield ModuleImport(
                            self.imported_name(package, alias.name), statement
                        )

    def imported_name(self, package: str, name: str) -> str:
        """
        :param package: The dotted name within ``basstler`` a ``from`` import reads from.
        :param name: A name it imports.
        :return: The module *name* is, when it is one, else *package*.
        """
        candidate = ".".join(part for part in (package, name) if part)
        location = Path(*candidate.split("."))
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
