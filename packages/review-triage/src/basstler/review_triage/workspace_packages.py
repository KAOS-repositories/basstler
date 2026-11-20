"""
The plan splitting the single ``basstler`` package into a directory per distribution,
built from the tree it is applied to and read without importing any of it.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from basstler.code_modification.actions import Action, ActionPlan, PlanBuilder
from basstler.code_modification.file_actions import (
    FileCreation,
    FileDeletion,
    FileMove,
)
from basstler.code_modification.module_relocation import ImportRoots, ModuleRelocation
from basstler.code_modification.source_tree import SourceTree
from basstler.locations import SinglePackageLocation, WorkspaceLocation
from basstler.review_triage.commit_tree import MODULE_SUFFIX, PACKAGE_INITIALIZER

NAMESPACE = "basstler"
"""
The package every distribution ships a part of, and the meta-package's name.
"""

DISTRIBUTION_PREFIX = f"{NAMESPACE}-"
"""
What every distribution's name but the meta-package's starts with, which its directory
leaves out.
"""

TEST_SUPPORT = "test support"
"""
Where a test helper goes when the tests of several distributions use it, in place of a
distribution's name.
"""

TEST_PREFIX = "test_"
"""
What the name of a module holding tests starts with.
"""

# %% the distributions the tree declares


@dataclass(frozen=True)
class DeclaredDistributions:
    """
    The distribution each module of the package belongs to, as the tree's package map
    declares it.
    """

    distributions: Mapping[str, str]
    """
    The distribution's name, by the dotted name within the package of each module or
    subpackage it ships.
    """

    @classmethod
    def read(cls, tree: SourceTree) -> DeclaredDistributions:
        """
        :param tree: A tree holding :attr:`SinglePackageLocation.PACKAGE_MAP`.
        :return: The distributions its ``DistributionDeclaration`` calls declare.
        :raises KeyError: If the tree holds no package map.
        """
        module = ast.parse(tree.files[SinglePackageLocation.PACKAGE_MAP])
        names = {
            statement.targets[0].id: statement.value.value
            for node in ast.walk(module)
            if isinstance(node, ast.ClassDef) and node.name == "Distribution"
            for statement in node.body
            if isinstance(statement, ast.Assign)
            and isinstance(statement.value, ast.Constant)
        }
        distributions = {}
        for node in ast.walk(module):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "DistributionDeclaration"
            ):
                continue
            distribution = names[node.args[0].attr]
            modules = next(
                argument
                for argument in node.args
                if isinstance(argument, ast.Tuple)
                and all(isinstance(element, ast.Constant) for element in argument.elts)
            )
            for element in modules.elts:
                distributions[element.value] = distribution
        return cls(distributions)

    def distribution_of(self, module: tuple[str, ...]) -> str | None:
        """
        :param module: A dotted name within the package, split at its dots.
        :return: The distribution of the longest declared name *module* starts with,
            ``None`` when none is declared.
        """
        return next(
            (
                self.distributions[".".join(module[:length])]
                for length in range(len(module), 0, -1)
                if ".".join(module[:length]) in self.distributions
            ),
            None,
        )

    @property
    def directories(self) -> frozenset[str]:
        """
        The directory under :attr:`WorkspaceLocation.PACKAGES` of each distribution.
        """
        return frozenset(
            directory_name(distribution) for distribution in self.distributions.values()
        )


def directory_name(distribution: str) -> str:
    """
    :param distribution: A distribution's name.
    :return: Its directory under :attr:`WorkspaceLocation.PACKAGES`.
    """
    return distribution.removeprefix(DISTRIBUTION_PREFIX)


# %% the templates


@dataclass(frozen=True)
class TemplateReaders:
    """
    The distribution whose modules name each template of the tree.
    """

    tree: SourceTree
    """
    The single-package tree.
    """

    declared: DeclaredDistributions
    """
    The distribution of each of its modules.
    """

    def distribution_of(self, template: str) -> str | None:
        """
        :param template: A template's file name.
        :return: The one distribution whose modules name the template, through the
            class of :attr:`SinglePackageLocation.LOCATIONS` that holds it or as a
            string; ``None`` when no single one does.
        """
        holder = self.holding_classes.get(template)
        readers = self.name_readers.get(holder, frozenset()) if holder else frozenset()
        readers = readers or self.literal_readers.get(template, frozenset())
        return next(iter(readers)) if len(readers) == 1 else None

    @cached_property
    def holding_classes(self) -> dict[str, str]:
        """
        The class of :attr:`SinglePackageLocation.LOCATIONS` naming each template.
        """
        module = ast.parse(self.tree.files[SinglePackageLocation.LOCATIONS])
        return {
            constant.value: node.name
            for node in module.body
            if isinstance(node, ast.ClassDef)
            for constant in ast.walk(node)
            if isinstance(constant, ast.Constant)
            and isinstance(constant.value, str)
            and SinglePackageLocation.TEMPLATES / constant.value in self.tree.files
        }

    @cached_property
    def name_readers(self) -> dict[str, frozenset[str]]:
        """
        The distributions whose modules use each name.
        """
        return self.readers(
            lambda node: node.id if isinstance(node, ast.Name) else None
        )

    @cached_property
    def literal_readers(self) -> dict[str, frozenset[str]]:
        """
        The distributions whose modules hold each string.
        """
        return self.readers(
            lambda node: (
                node.value
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
                else None
            )
        )

    def readers(
        self, word_of: Callable[[ast.AST], str | None]
    ) -> dict[str, frozenset[str]]:
        """
        :param word_of: The word a syntax node holds, ``None`` for a node holding none.
        :return: The distributions whose modules, the locations module aside, hold
            each word.
        """
        readers: dict[str, set[str]] = {}
        for path, content in self.tree.files.items():
            distribution = source_distribution(self.declared, path)
            if (
                distribution is None
                or path.suffix != MODULE_SUFFIX
                or path == SinglePackageLocation.LOCATIONS
            ):
                continue
            for node in ast.walk(ast.parse(content)):
                word = word_of(node)
                if word is not None:
                    readers.setdefault(word, set()).add(distribution)
        return {word: frozenset(found) for word, found in readers.items()}


def source_distribution(declared: DeclaredDistributions, path: Path) -> str | None:
    """
    :param declared: The distribution of each module.
    :param path: A file of the tree.
    :return: The distribution of the module or subpackage holding *path* under
        :attr:`SinglePackageLocation.SOURCE`, ``None`` for a file outside one.
    """
    if not path.is_relative_to(SinglePackageLocation.SOURCE):
        return None
    relative = path.relative_to(SinglePackageLocation.SOURCE)
    if len(relative.parts) == 1:
        return declared.distribution_of((relative.stem,))
    return declared.distribution_of(relative.parent.parts)


# %% the tests and their helpers


@dataclass(frozen=True)
class TestHomes:
    """
    The distribution, or :data:`TEST_SUPPORT`, each Python file of the tests' package
    goes to.
    """

    tree: SourceTree
    """
    The single-package tree.
    """

    declared: DeclaredDistributions
    """
    The distribution of each of its modules.
    """

    def home_of(self, path: Path) -> str | None:
        """
        :param path: A file under :attr:`SinglePackageLocation.TESTS`.
        :return: Where it goes: the distribution whose tests it is or helps, or
            :data:`TEST_SUPPORT`; ``None`` for a helper no test imports.
        """
        if path in self.helpers:
            return self.helper_homes.get(path)
        relative = path.relative_to(SinglePackageLocation.TESTS)
        if path == SinglePackageLocation.SHARED_FIXTURES or relative.parts[0] in (
            SinglePackageLocation.DATASET.name,
            SinglePackageLocation.TEST_CONSTANTS.name,
        ):
            return TEST_SUPPORT
        tested = (
            relative.parts[0]
            if len(relative.parts) > 1
            else relative.stem.removeprefix(TEST_PREFIX)
        )
        return self.declared.distribution_of((tested,)) or NAMESPACE

    @cached_property
    def helpers(self) -> frozenset[Path]:
        """
        The modules of the tests' package that hold no tests: neither a test module, a
        package initializer, a ``conftest`` nor a file of the shared directories.
        """
        return frozenset(
            path
            for path in self.modules.values()
            if not path.name.startswith(TEST_PREFIX)
            and path.name
            not in (PACKAGE_INITIALIZER, SinglePackageLocation.SHARED_FIXTURES.name)
            and path.relative_to(SinglePackageLocation.TESTS).parts[0]
            not in (
                SinglePackageLocation.DATASET.name,
                SinglePackageLocation.TEST_CONSTANTS.name,
            )
        )

    @cached_property
    def modules(self) -> dict[str, Path]:
        """
        The Python files of the tests' package outside its dataset, by dotted name.
        """
        return {
            module_name(path): path
            for path in self.tree.files
            if path.suffix == MODULE_SUFFIX
            and path.is_relative_to(SinglePackageLocation.TESTS)
            and not path.is_relative_to(SinglePackageLocation.DATASET)
        }

    @cached_property
    def importers(self) -> dict[Path, frozenset[Path]]:
        """
        The files of :attr:`modules` importing each one.
        """
        importers: dict[Path, set[Path]] = {}
        for importer in self.modules.values():
            for imported in self.imported_by(importer):
                importers.setdefault(imported, set()).add(importer)
        return {path: frozenset(found) for path, found in importers.items()}

    def imported_by(self, importer: Path) -> Iterator[Path]:
        """
        :param importer: A file of :attr:`modules`.
        :return: The files of :attr:`modules` it imports.
        """
        name = module_name(importer).split(".")
        package = name if importer.name == PACKAGE_INITIALIZER else name[:-1]
        for node in ast.walk(ast.parse(self.tree.files[importer])):
            if isinstance(node, ast.ImportFrom):
                base = package[: len(package) - node.level + 1] if node.level else []
                written = ".".join([*base, *([node.module] if node.module else [])])
                for candidate in (
                    written,
                    *(f"{written}.{alias.name}" for alias in node.names),
                ):
                    if candidate in self.modules:
                        yield self.modules[candidate]
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.modules:
                        yield self.modules[alias.name]

    @cached_property
    def helper_homes(self) -> dict[Path, str]:
        """
        Where each helper some test imports goes: the one place every file importing it
        goes, or :data:`TEST_SUPPORT` when they go to several.
        """
        homes: dict[Path, str] = {}
        for helper in sorted(self.helpers):
            found = self.importer_homes(helper, frozenset({helper}))
            if found:
                homes[helper] = next(iter(found)) if len(found) == 1 else TEST_SUPPORT
        return homes

    def importer_homes(self, helper: Path, seen: frozenset[Path]) -> frozenset[str]:
        """
        :param helper: A helper.
        :param seen: The helpers already followed, so an import cycle ends.
        :return: Where the files importing *helper* go, a helper importing it counting
            for where the files importing that helper go.
        """
        homes: set[str] = set()
        for importer in self.importers.get(helper, frozenset()) - seen:
            if importer in self.helpers:
                homes |= self.importer_homes(importer, seen | {importer})
            elif importer.name != PACKAGE_INITIALIZER:
                homes.add(self.home_of(importer))
        return frozenset(homes)


def module_name(path: Path) -> str:
    """
    :param path: A Python file of the tests' package.
    :return: The dotted name it is imported by.
    """
    parts = path.with_suffix("").parts
    return ".".join(parts[:-1] if path.name == PACKAGE_INITIALIZER else parts)


# %% the plan


@dataclass(frozen=True)
class PackageSplit:
    """
    Where each file of a single-package tree goes once the tree is split into a
    directory per distribution.
    """

    tree: SourceTree
    """
    The single-package tree.
    """

    @cached_property
    def declared(self) -> DeclaredDistributions:
        """
        The distribution of each module, as the tree's package map declares it.
        """
        return DeclaredDistributions.read(self.tree)

    def destination(self, path: Path) -> Path | None:
        """
        :param path: A file of the tree.
        :return: Where it goes, ``None`` for a file that stays where it is.
        """
        if path.is_relative_to(SinglePackageLocation.TEMPLATES):
            distribution = self.template_readers.distribution_of(path.name)
            return self.source_path(distribution, path)
        if path.is_relative_to(SinglePackageLocation.SOURCE):
            return self.source_path(source_distribution(self.declared, path), path)
        if path.is_relative_to(SinglePackageLocation.TESTS):
            return self.test_path(self.test_homes.home_of(path), path)
        return None

    @cached_property
    def template_readers(self) -> TemplateReaders:
        """
        The distribution reading each template.
        """
        return TemplateReaders(self.tree, self.declared)

    @cached_property
    def test_homes(self) -> TestHomes:
        """
        Where each file of the tests' package goes.
        """
        return TestHomes(self.tree, self.declared)

    @staticmethod
    def source_path(distribution: str | None, path: Path) -> Path | None:
        """
        :param distribution: The distribution shipping *path*, or ``None``.
        :param path: A file under :attr:`SinglePackageLocation.SOURCE`.
        :return: Its path in the distribution's part of the package.
        """
        if distribution is None:
            return None
        return (
            WorkspaceLocation.PACKAGES
            / directory_name(distribution)
            / WorkspaceLocation.PACKAGE_SOURCE
            / path.relative_to(SinglePackageLocation.SOURCE)
        )

    @staticmethod
    def test_path(home: str | None, path: Path) -> Path | None:
        """
        :param home: Where *path* goes, or ``None``.
        :param path: A file under :attr:`SinglePackageLocation.TESTS`.
        :return: Its path in the distribution's tests or in the shared test support.
        """
        if home is None:
            return None
        if path == SinglePackageLocation.SHARED_FIXTURES:
            return Path(WorkspaceLocation.SHARED_FIXTURES)
        relative = path.relative_to(SinglePackageLocation.TESTS)
        if home == TEST_SUPPORT:
            return WorkspaceLocation.TEST_SUPPORT_PACKAGE / relative
        return (
            WorkspaceLocation.PACKAGES
            / directory_name(home)
            / WorkspaceLocation.PACKAGE_TESTS
            / relative
        )

    @property
    def import_roots(self) -> ImportRoots:
        """
        Where modules are imported from, before the split and after it.
        """
        return ImportRoots(
            (
                SinglePackageLocation.SOURCE.parent,
                Path(),
                Path(WorkspaceLocation.TEST_SUPPORT),
                *(
                    root
                    for directory in sorted(self.declared.directories)
                    for root in (
                        WorkspaceLocation.PACKAGES / directory,
                        WorkspaceLocation.PACKAGES
                        / directory
                        / WorkspaceLocation.PACKAGE_SOURCE.parent,
                    )
                ),
            )
        )


@dataclass(frozen=True)
class WorkspacePackagesPlan(PlanBuilder[SourceTree]):
    """
    Moves every module, template and test of the single package into the directory of
    its distribution, and the helpers the tests of several distributions share into the
    test support; rewrites the imports the moves break and makes the package a namespace
    package.
    """

    def build(self, target: SourceTree) -> Action[SourceTree]:
        split = PackageSplit(target)
        moves = tuple(
            FileMove(path, destination)
            for path in sorted(target.files)
            if path not in self.removed
            and (destination := split.destination(path)) not in (None, path)
        )
        destinations = {move.destination for move in moves} | (
            target.files.keys() - {move.source for move in moves} - set(self.removed)
        )
        return ActionPlan(
            (
                *(
                    FileDeletion(path, target.files[path])
                    for path in self.removed
                    if path in target.files
                ),
                ModuleRelocation(moves, split.import_roots),
                *(
                    FileCreation(path, b"")
                    for path in sorted(self.package_initializers(destinations))
                ),
            )
        )

    @property
    def removed(self) -> tuple[Path, ...]:
        """
        The package initializers the split leaves without a package of their own.
        """
        return (
            Path(SinglePackageLocation.PACKAGE_INITIALIZER),
            Path(SinglePackageLocation.TESTS_INITIALIZER),
        )

    @staticmethod
    def package_initializers(paths: set[Path]) -> set[Path]:
        """
        :param paths: The files of the split tree.
        :return: The empty initializers the split tree lacks: one in each directory of
            a distribution's tests or of the test support that holds a Python module, and
            in each directory between it and the tests' root.
        """
        roots = {
            Path(*path.parts[:3])
            for path in paths
            if path.is_relative_to(WorkspaceLocation.PACKAGES)
            and len(path.parts) > 3
            and path.parts[2] == WorkspaceLocation.PACKAGE_TESTS.name
        } | {Path(WorkspaceLocation.TEST_SUPPORT_PACKAGE)}
        dataset = (
            WorkspaceLocation.TEST_SUPPORT_PACKAGE / SinglePackageLocation.DATASET.name
        )
        needed = set()
        for path in paths:
            if path.suffix != MODULE_SUFFIX or path.is_relative_to(dataset):
                continue
            root = next((root for root in roots if path.is_relative_to(root)), None)
            if root is None:
                continue
            directory = path.parent
            while directory.is_relative_to(root):
                needed.add(directory / PACKAGE_INITIALIZER)
                directory = directory.parent
        return needed - paths
