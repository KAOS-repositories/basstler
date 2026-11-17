"""
Renaming a symbol everywhere a module names it.
"""

from __future__ import annotations

from dataclasses import dataclass

import libcst
from libcst.metadata import CodeRange

from basstler.code_modification.actions import (
    Action,
    ActionPlan,
    AppliedAction,
    NodeReplacement,
)
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.specification import Specification

# %% the places


@dataclass(frozen=True)
class NameOccurrence(Specification):
    """
    One place where a module names the symbol being renamed.
    """

    node: libcst.Name
    """
    The name at that place: an import, a definition, a base class, an annotation, a call
    or an attribute.
    """


class NameCollector(libcst.CSTVisitor):
    """
    Collects the names of a module that spell one identifier.
    """

    def __init__(self, identifier: str) -> None:
        """
        :param identifier: The identifier whose names are collected.
        """
        self.identifier = identifier
        self.names: list[libcst.Name] = []

    def visit_Name(self, node: libcst.Name) -> None:
        if node.value == self.identifier:
            self.names.append(node)


# %% the rename


@dataclass(frozen=True)
class SymbolRename(Action):
    """
    Renames a symbol wherever a module names it. Text that only mentions the old name,
    such as a docstring, a comment or a string, is left as it is.
    """

    old_name: str
    """
    The identifier being replaced.
    """

    new_name: str
    """
    The identifier that replaces it.
    """

    def occurrences(self, *, module: PositionedModule) -> list[NameOccurrence]:
        """
        :param module: The module to search.
        :return: Every place *module* names :attr:`old_name`, in source order.
        """
        collector = NameCollector(self.old_name)
        module.module.visit(collector)
        locations: dict[libcst.Name, CodeRange] = {
            name: module.positions[name] for name in collector.names
        }
        return [
            NameOccurrence(location=location, node=name)
            for name, location in sorted(
                locations.items(),
                key=lambda item: (item[1].start.line, item[1].start.column),
            )
        ]

    def apply(self, module: libcst.Module) -> AppliedAction:
        replacements = [
            NodeReplacement(
                occurrence.location,
                occurrence.node,
                occurrence.node.with_changes(value=self.new_name),
            )
            for occurrence in reversed(
                self.occurrences(module=PositionedModule(module))
            )
        ]
        return ActionPlan(tuple(replacements)).apply(module)
