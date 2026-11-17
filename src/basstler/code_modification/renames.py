"""
Renaming a symbol everywhere a module names it.
"""

from __future__ import annotations

import re
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


@dataclass(frozen=True)
class MentionOccurrence(Specification):
    """
    One comment or string that mentions the symbol being renamed as a whole word.
    """

    node: libcst.Comment | libcst.SimpleString
    """
    The comment, or the string literal such as a docstring, holding the mention.
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


class MentionCollector(libcst.CSTVisitor):
    """
    Collects the comments and strings of a module that mention one identifier.
    """

    def __init__(self, pattern: re.Pattern[str]) -> None:
        """
        :param pattern: What a mention looks like.
        """
        self.pattern = pattern
        self.nodes: list[libcst.Comment | libcst.SimpleString] = []

    def visit_Comment(self, node: libcst.Comment) -> None:
        if self.pattern.search(node.value):
            self.nodes.append(node)

    def visit_SimpleString(self, node: libcst.SimpleString) -> None:
        if self.pattern.search(node.value):
            self.nodes.append(node)


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

    include_mentions: bool = False
    """
    Whether a comment or a string that mentions :attr:`old_name` as a whole word, such
    as a docstring, names :attr:`new_name` too.
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

    @property
    def mention_pattern(self) -> re.Pattern[str]:
        """
        :return: What a mention of :attr:`old_name` looks like: the identifier, not
            part of a longer one.
        """
        return re.compile(
            rf"(?<![A-Za-z0-9_]){re.escape(self.old_name)}(?![A-Za-z0-9_])"
        )

    def mentions(self, *, module: PositionedModule) -> list[MentionOccurrence]:
        """
        :param module: The module to search.
        :return: Every comment and string of *module* that mentions :attr:`old_name`.
        """
        collector = MentionCollector(self.mention_pattern)
        module.module.visit(collector)
        return [
            MentionOccurrence(location=module.positions[node], node=node)
            for node in collector.nodes
        ]

    def apply(self, module: libcst.Module) -> AppliedAction:
        positioned = PositionedModule(module)
        replacements = [
            NodeReplacement(
                occurrence.location,
                occurrence.node,
                occurrence.node.with_changes(value=self.new_name),
            )
            for occurrence in self.occurrences(module=positioned)
        ]
        if self.include_mentions:
            replacements += [
                NodeReplacement(
                    mention.location,
                    mention.node,
                    mention.node.with_changes(
                        value=self.mention_pattern.sub(
                            self.new_name, mention.node.value
                        )
                    ),
                )
                for mention in self.mentions(module=positioned)
            ]
        replacements.sort(
            key=lambda replacement: (
                replacement.location.start.line,
                replacement.location.start.column,
            ),
            reverse=True,
        )
        return ActionPlan(tuple(replacements)).apply(module)
