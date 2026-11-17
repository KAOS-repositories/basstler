"""
Importing a name from the module it moved to.
"""

from __future__ import annotations

from dataclasses import dataclass

import libcst
from libcst.helpers import get_full_name_for_node
from libcst.metadata import CodeRange

from basstler.code_modification.actions import (
    Action,
    ActionPlan,
    AppliedAction,
    NodeReplacement,
)
from basstler.code_modification.exceptions import ImportRelocationUnsupportedError
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.specification import Specification

# %% the places


@dataclass(frozen=True)
class ImportOccurrence(Specification):
    """
    One ``from <module> import <name>`` statement of the name being relocated.
    """

    node: libcst.ImportFrom
    """
    The statement.
    """


class ImportCollector(libcst.CSTVisitor):
    """
    Collects the ``from`` imports of a module that import from one module.
    """

    def __init__(self, module_name: str) -> None:
        """
        :param module_name: The dotted name of the module imported from.
        """
        self.module_name = module_name
        self.imports: list[libcst.ImportFrom] = []

    def visit_ImportFrom(self, node: libcst.ImportFrom) -> None:
        if node.relative or node.module is None:
            return
        if get_full_name_for_node(node.module) == self.module_name:
            self.imports.append(node)


# %% the relocation


@dataclass(frozen=True)
class ImportRelocation(Action):
    """
    Imports a name from the module it moved to, wherever a module imports it from the
    module it moved out of. An alias is kept.
    """

    name: str
    """
    The name that moved.
    """

    old_module: str
    """
    The dotted name of the module it moved out of.
    """

    new_module: str
    """
    The dotted name of the module it moved to.
    """

    def occurrences(self, *, module: PositionedModule) -> list[ImportOccurrence]:
        """
        :param module: The module to search.
        :return: Every statement of *module* importing :attr:`name` from
            :attr:`old_module`, in source order.
        :raises ImportRelocationUnsupportedError: If such a statement also imports other
            names.
        """
        collector = ImportCollector(self.old_module)
        module.module.visit(collector)
        occurrences = []
        for statement in collector.imports:
            if isinstance(statement.names, libcst.ImportStar):
                continue
            imported = [get_full_name_for_node(alias.name) for alias in statement.names]
            if self.name not in imported:
                continue
            location: CodeRange = module.positions[statement]
            if len(imported) > 1:
                raise ImportRelocationUnsupportedError(location)
            occurrences.append(ImportOccurrence(location=location, node=statement))
        return sorted(
            occurrences,
            key=lambda occurrence: (
                occurrence.location.start.line,
                occurrence.location.start.column,
            ),
        )

    def apply(self, module: libcst.Module) -> AppliedAction:
        new_module_node = libcst.parse_expression(self.new_module)
        replacements = [
            NodeReplacement(
                occurrence.location,
                occurrence.node,
                occurrence.node.with_changes(module=new_module_node),
            )
            for occurrence in reversed(
                self.occurrences(module=PositionedModule(module))
            )
        ]
        return ActionPlan(tuple(replacements)).apply(module)
