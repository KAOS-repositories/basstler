"""
Moving modules within a source tree together with every import the move would break.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import libcst
from libcst.helpers import get_full_name_for_node
from libcst.metadata import CodeRange

from basstler.code_modification.actions import (
    Action,
    ActionPlan,
    AppliedAction,
    NodeReplacement,
)
from basstler.code_modification.exceptions import UnrewritableImportError
from basstler.code_modification.file_actions import FileMove, ModuleEdit
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.source_tree import SourceTree

# %% module names


@dataclass(frozen=True)
class ImportRoots:
    """
    The directories of a tree that modules are imported from, as on ``sys.path``.
    """

    directories: tuple[Path, ...]
    """
    Each directory, relative to the tree's root; a file is named from the deepest one
    holding it.
    """

    def module_name(self, path: Path) -> str | None:
        """
        :param path: A file of the tree, relative to its root.
        :return: The dotted name *path* is imported by; none for a file that is not a
            Python module under one of :attr:`directories`.
        """
        roots = [root for root in self.directories if path.is_relative_to(root)]
        if path.suffix != ".py" or not roots:
            return None
        root = max(roots, key=lambda directory: len(directory.parts))
        parts = path.relative_to(root).with_suffix("").parts
        return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


@dataclass(frozen=True)
class ModuleLocation:
    """
    Where one module of the tree lies, before and after a relocation.
    """

    old_name: str
    """
    The dotted name it is imported by before the relocation.
    """

    new_name: str
    """
    The dotted name it is imported by after the relocation.
    """

    is_package: bool
    """
    Whether the module is a package's ``__init__``, from which relative imports start.
    """

    def base_of(self, statement: libcst.ImportFrom, importer_name: str) -> str:
        """
        :param statement: An import in this module.
        :param importer_name: This module's name, before or after the relocation.
        :return: The dotted name of the module *statement* imports from.
        """
        written = get_full_name_for_node(statement.module) if statement.module else ""
        level = len(statement.relative)
        if not level:
            return written
        package = importer_name.split(".")
        if not self.is_package:
            package = package[:-1]
        parts = package[: len(package) - level + 1]
        return ".".join([*parts, written] if written else parts)


# %% the relocation


@dataclass(frozen=True)
class ModuleRelocation(Action[SourceTree]):
    """
    Moves files of a tree and rewrites, as an absolute import, every import that would
    no longer reach the module it imported.
    """

    moves: tuple[FileMove, ...]
    """
    The files moved.
    """

    import_roots: ImportRoots
    """
    The directories the tree's modules are imported from, before and after the moves.
    """

    def apply(self, target: SourceTree) -> AppliedAction[SourceTree]:
        rewrites = tuple(self.import_rewrites(target))
        return ActionPlan((*self.moves, *rewrites)).apply(target)

    @cached_property
    def destinations(self) -> Mapping[Path, Path]:
        """
        Where each moved file goes, by where it was.
        """
        return {move.source: move.destination for move in self.moves}

    def locations(self, tree: SourceTree) -> dict[str, ModuleLocation]:
        """
        :param tree: The tree before the moves.
        :return: Where each module of *tree* lies before and after the moves, by its
            name before them.
        """
        locations = {}
        for path in tree.files:
            old_name = self.import_roots.module_name(path)
            new_name = self.import_roots.module_name(self.destinations.get(path, path))
            if old_name is not None and new_name is not None:
                locations[old_name] = ModuleLocation(
                    old_name, new_name, path.name == "__init__.py"
                )
        return locations

    def import_rewrites(self, tree: SourceTree) -> Iterator[ModuleEdit]:
        """
        :param tree: The tree before the moves.
        :return: An edit of each module, at its path after the moves, rewriting the
            imports the moves break.
        """
        locations = self.locations(tree)
        for path, content in tree.files.items():
            importer = locations.get(self.import_roots.module_name(path) or "")
            if importer is None:
                continue
            module = PositionedModule(
                libcst.parse_module(content.decode(encoding="utf-8"))
            )
            replacements = sorted(
                ImportRewriter(path, importer, locations).replacements(module),
                key=lambda replacement: (
                    replacement.location.start.line,
                    replacement.location.start.column,
                ),
                reverse=True,
            )
            if replacements:
                yield ModuleEdit(
                    self.destinations.get(path, path), ActionPlan(tuple(replacements))
                )


# %% rewriting one module's imports


@dataclass(frozen=True)
class ImportRewriter:
    """
    Finds the imports of one module that a relocation breaks, and their rewrites.
    """

    path: Path
    """
    The module's path before the relocation, relative to the tree's root.
    """

    importer: ModuleLocation
    """
    Where the module lies before and after the relocation.
    """

    locations: Mapping[str, ModuleLocation]
    """
    Where every module of the tree lies, by its name before the relocation.
    """

    def replacements(self, module: PositionedModule) -> Iterator[NodeReplacement]:
        """
        :param module: The module, as it is before the relocation.
        :return: A replacement of each import of it that the relocation breaks.
        :raises UnrewritableImportError: If a broken import binds a name no rewrite of
            the statement keeps.
        """
        for node, location in module.positions.items():
            if isinstance(node, libcst.ImportFrom):
                yield from self.from_import_replacements(node, location)
            if isinstance(node, libcst.Import):
                yield from self.import_replacements(node, location)

    def from_import_replacements(
        self, statement: libcst.ImportFrom, location: CodeRange
    ) -> Iterator[NodeReplacement]:
        """
        :param statement: A ``from`` import of the module.
        :param location: Where it lies in the module.
        :return: Its rewrite as an absolute import of where its module went, when it no
            longer reaches that module where it is written.
        """
        imported = self.locations.get(
            self.importer.base_of(statement, self.importer.old_name)
        )
        if imported is None:
            return
        if self.importer.base_of(statement, self.importer.new_name) == (
            imported.new_name
        ):
            return
        yield NodeReplacement(
            location,
            statement,
            statement.with_changes(
                module=libcst.parse_expression(imported.new_name), relative=()
            ),
        )

    def import_replacements(
        self, statement: libcst.Import, location: CodeRange
    ) -> Iterator[NodeReplacement]:
        """
        :param statement: A plain import in the module.
        :param location: Where it lies in the module.
        :return: Its rewrite naming each moved module it imports where it went.
        :raises UnrewritableImportError: If it imports a moved module without an alias.
        """
        names = []
        for alias in statement.names:
            name = get_full_name_for_node(alias.name)
            imported = self.locations.get(name)
            if imported is None or imported.new_name == name:
                names.append(alias)
                continue
            if alias.asname is None:
                raise UnrewritableImportError(self.path, location.start.line, name)
            names.append(
                alias.with_changes(name=libcst.parse_expression(imported.new_name))
            )
        if names != list(statement.names):
            yield NodeReplacement(
                location, statement, statement.with_changes(names=names)
            )
