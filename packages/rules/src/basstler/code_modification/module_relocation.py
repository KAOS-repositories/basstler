"""
Moving modules within a source tree together with every import the move would break.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import libcst
from libcst.helpers import get_full_name_for_node

from basstler.code_modification.actions import (
    Action,
    ActionPlan,
    AppliedAction,
    ModuleTransformation,
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
            parsed = libcst.parse_module(content.decode(encoding="utf-8"))
            rewriter = ImportRewriter(path, importer, locations)
            if not rewriter.breaks_any(parsed):
                continue
            yield ModuleEdit(self.destinations.get(path, path), ImportRewrite(rewriter))


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

    def breaks_any(self, module: libcst.Module) -> bool:
        """
        :param module: The module, as it is before the relocation.
        :return: Whether the relocation breaks one of its imports.
        """
        collector = ImportCollector()
        module.visit(collector)
        return any(self.breaks(statement) for statement in collector.statements)

    def breaks(self, statement: libcst.Import | libcst.ImportFrom) -> bool:
        """
        :param statement: An import of the module.
        :return: Whether the relocation leaves it importing a module no longer there.
        """
        if isinstance(statement, libcst.ImportFrom):
            return self.moved_base(statement) is not None
        return any(self.moved_module(alias) is not None for alias in statement.names)

    def moved_base(self, statement: libcst.ImportFrom) -> ModuleLocation | None:
        """
        :param statement: A ``from`` import of the module.
        :return: Where the module it imports from lies, when the relocation leaves the
            statement no longer reaching it; ``None`` otherwise.
        """
        imported = self.locations.get(
            self.importer.base_of(statement, self.importer.old_name)
        )
        if imported is None or (
            self.importer.base_of(statement, self.importer.new_name)
            == imported.new_name
        ):
            return None
        return imported

    def moved_module(self, alias: libcst.ImportAlias) -> ModuleLocation | None:
        """
        :param alias: A name a plain import of the module imports.
        :return: Where that module lies, when the relocation renames it; ``None``
            otherwise.
        """
        imported = self.locations.get(get_full_name_for_node(alias.name))
        if imported is None or imported.new_name == imported.old_name:
            return None
        return imported

    def rewritten(
        self, statement: libcst.Import | libcst.ImportFrom, module: libcst.Module
    ) -> libcst.Import | libcst.ImportFrom | None:
        """
        :param statement: An import of *module*.
        :param module: The module, as it is before the relocation.
        :return: The statement importing, by an absolute name, every moved module it
            imports where it went; ``None`` when the relocation breaks none of it.
        :raises UnrewritableImportError: If it imports a moved module by its dotted name
            without an alias.
        """
        if isinstance(statement, libcst.ImportFrom):
            imported = self.moved_base(statement)
            if imported is None:
                return None
            return statement.with_changes(
                module=libcst.parse_expression(imported.new_name), relative=()
            )
        names = []
        for alias in statement.names:
            imported = self.moved_module(alias)
            if imported is None:
                names.append(alias)
                continue
            if alias.asname is None:
                line = PositionedModule(module).positions[statement].start.line
                raise UnrewritableImportError(self.path, line, imported.old_name)
            names.append(
                alias.with_changes(name=libcst.parse_expression(imported.new_name))
            )
        if names == list(statement.names):
            return None
        return statement.with_changes(names=names)


@dataclass(frozen=True)
class ImportRewrite(ModuleTransformation):
    """
    Rewrites the imports of one module that a relocation breaks.
    """

    rewriter: ImportRewriter
    """
    Finds those imports and their rewrites.
    """

    def transform(self, module: libcst.Module) -> libcst.Module:
        return libcst.ensure_type(
            module.visit(ImportRewriting(self.rewriter, module)), libcst.Module
        )


@dataclass
class ImportRewriting(libcst.CSTTransformer):
    """
    Puts its rewrite in the place of each import of one module a relocation breaks.
    """

    rewriter: ImportRewriter
    """
    Finds the imports and their rewrites.
    """

    module: libcst.Module
    """
    The module visited, as it is before the relocation.
    """

    def __post_init__(self) -> None:
        """
        Initialise the transformer, which the dataclass's generated initialiser skips.
        """
        super().__init__()

    def on_visit(self, node: libcst.CSTNode) -> bool:
        """
        :param node: A node of the module visited.
        :return: Whether to visit its children too: not for an expression, which holds
            no import.
        """
        return not isinstance(node, libcst.BaseExpression)

    def on_leave(
        self, original_node: libcst.CSTNode, updated_node: libcst.CSTNode
    ) -> libcst.CSTNode:
        """
        :param original_node: A node of the module visited.
        :param updated_node: That node with its children rewritten.
        :return: The rewrite of *original_node* when it is a broken import, else
            *updated_node*.
        """
        if not isinstance(original_node, (libcst.Import, libcst.ImportFrom)):
            return updated_node
        return self.rewriter.rewritten(original_node, self.module) or updated_node


@dataclass
class ImportCollector(libcst.CSTVisitor):
    """
    Collects every import statement of a module, wherever it is nested.
    """

    statements: list[libcst.Import | libcst.ImportFrom] = field(default_factory=list)
    """
    The statements, in the order they are written.
    """

    def __post_init__(self) -> None:
        """
        Initialise the visitor, which the dataclass's generated initialiser skips.
        """
        super().__init__()

    def on_visit(self, node: libcst.CSTNode) -> bool:
        """
        :param node: A node of the module visited.
        :return: Whether to visit its children too: not for an expression, which holds
            no import.
        """
        if isinstance(node, (libcst.Import, libcst.ImportFrom)):
            self.statements.append(node)
        return not isinstance(node, libcst.BaseExpression)
