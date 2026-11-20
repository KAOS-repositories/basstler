"""
A Python source file parsed with libcst, which checkers query for the calls and returns
they report.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import override

import libcst
from libcst.metadata import (
    CodeRange,
    MetadataWrapper,
    PositionProvider,
    QualifiedNameProvider,
)

from basstler.class_property import classproperty

# %% resolving names


@dataclass(eq=False)
class QualifiedNameCollector(libcst.CSTVisitor):
    """
    Records the fully qualified names every name and attribute of a tree refers to.
    """

    names: dict[libcst.CSTNode, frozenset[str]] = field(
        default_factory=dict, init=False
    )
    """
    The names each visited node refers to.
    """

    @classproperty
    @override
    def METADATA_DEPENDENCIES(cls) -> tuple[type[QualifiedNameProvider]]:
        """
        The metadata :meth:`get_metadata` reads while visiting.
        """
        return (QualifiedNameProvider,)

    @override
    def on_visit(self, node: libcst.CSTNode) -> bool:
        if isinstance(node, libcst.Name | libcst.Attribute):
            self.names[node] = frozenset(
                qualified.name
                for qualified in self.get_metadata(QualifiedNameProvider, node, set())
            )
        return True


# %% the nodes checkers query


@dataclass(eq=False)
class QueriedNodeCollector(libcst.CSTVisitor):
    """
    Records every call and ``return`` statement of a tree, in the order they appear.
    """

    calls: list[libcst.Call] = field(default_factory=list, init=False)
    """
    The calls visited.
    """

    returns: list[libcst.Return] = field(default_factory=list, init=False)
    """
    The ``return`` statements visited.
    """

    @override
    def visit_Call(self, node: libcst.Call) -> None:
        self.calls.append(node)

    @override
    def visit_Return(self, node: libcst.Return) -> None:
        self.returns.append(node)


# %% the parsed file


@dataclass(frozen=True)
class SourceModule:
    """
    The syntax tree of one source file, with the position and the fully qualified name
    of every node.
    """

    path: Path
    """
    The source file.
    """

    @cached_property
    def source(self) -> bytes:
        """
        :return: The file's contents.
        """
        return self.path.read_bytes()

    @cached_property
    def wrapper(self) -> MetadataWrapper:
        """
        :return: The parsed file, which resolves metadata for its nodes.
        """
        return MetadataWrapper(libcst.parse_module(self.source), unsafe_skip_copy=True)

    @cached_property
    def positions(self) -> dict[libcst.CSTNode, CodeRange]:
        """
        :return: The lines each node of the file spans.
        """
        return self.wrapper.resolve(PositionProvider)

    @cached_property
    def qualified_names(self) -> dict[libcst.CSTNode, frozenset[str]]:
        """
        :return: The names each name or attribute refers to, resolved through the file's
            imports, as ``shutil.rmtree`` for ``rmtree`` after ``from shutil import rmtree``.
        """
        collector = QualifiedNameCollector()
        self.wrapper.visit(collector)
        return collector.names

    @cached_property
    def queried_nodes(self) -> QueriedNodeCollector:
        """
        :return: The calls and ``return`` statements of the file.
        """
        collector = QueriedNodeCollector()
        self.wrapper.module.visit(collector)
        return collector

    def calls(self) -> Iterator[libcst.Call]:
        """
        :return: Every call in the file.
        """
        return iter(self.queried_nodes.calls)

    def returns(self) -> Iterator[libcst.Return]:
        """
        :return: Every ``return`` statement in the file.
        """
        return iter(self.queried_nodes.returns)

    def refers_to(self, node: libcst.CSTNode, qualified_name: str) -> bool:
        """
        :return: Whether *node* names *qualified_name* or, for a module, something in it.
            A file that never spells the name's last part cannot refer to it.
        """
        last_part = qualified_name.rpartition(".")[2]
        if last_part.encode("utf-8") not in self.source:
            return False
        return any(
            name == qualified_name or name.startswith(f"{qualified_name}.")
            for name in self.qualified_names.get(node, frozenset())
        )

    def first_line(self, node: libcst.CSTNode) -> int:
        """
        :return: The line *node* starts on, counting from one.
        """
        return self.positions[node].start.line

    def last_line(self, node: libcst.CSTNode) -> int:
        """
        :return: The line *node* ends on, counting from one.
        """
        return self.positions[node].end.line
