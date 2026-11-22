"""
The patterns a syntax tree is searched for, each declared once as a libcst matcher.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

import libcst
from libcst import matchers
from libcst.metadata import CodeRange, MetadataWrapper

from basstler.class_property import classproperty
from basstler.code_modification.positions import PositionedModule

# %% occurrences


@dataclass(frozen=True)
class Occurrence:
    """
    A node that satisfies a pattern, and where it lies in its module.
    """

    node: libcst.CSTNode
    """
    The node.
    """

    location: CodeRange
    """
    The code range of :attr:`node`.
    """


# %% patterns


class CodePattern(ABC):
    """
    A shape of code, which the nodes of a syntax tree either have or lack.
    """

    @classproperty
    @abstractmethod
    def matcher(cls) -> matchers.BaseMatcherNode | matchers.OneOf | matchers.AllOf:
        """
        The matcher the nodes of the pattern satisfy; one pattern builds on another
        through the other's matcher.
        """

    @classmethod
    def matches(
        cls, node: libcst.CSTNode, metadata: MetadataWrapper | None = None
    ) -> bool:
        """
        :param metadata: Resolves the metadata of *node*, which only a pattern matching
            on metadata needs.
        :return: Whether *node* has the shape of the pattern.
        """
        return matchers.matches(node, cls.matcher, metadata_resolver=metadata)

    @classmethod
    def captures(
        cls, node: libcst.CSTNode, metadata: MetadataWrapper | None = None
    ) -> Mapping[str, libcst.CSTNode | Sequence[libcst.CSTNode]] | None:
        """
        :param metadata: Resolves the metadata of *node*, which only a pattern matching
            on metadata needs.
        :return: The nodes *node* holds that the matcher saved by name; ``None`` where
            *node* lacks the shape of the pattern.
        """
        return matchers.extract(node, cls.matcher, metadata_resolver=metadata)

    @classmethod
    def found_in(cls, module: PositionedModule) -> Iterator[Occurrence]:
        """
        :return: Every node of *module* with the shape of the pattern, in the order of
            the source.
        """
        for node in matchers.findall(
            module.module, cls.matcher, metadata_resolver=module.metadata
        ):
            yield Occurrence(node, module.positions[node])
