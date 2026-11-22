"""
A parsed Python module and where each of its nodes lies in its source.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property

import libcst
from libcst.metadata import CodeRange, MetadataWrapper, PositionProvider


@dataclass(frozen=True)
class PositionedModule:
    """
    A module's concrete syntax tree, with the code range each of its nodes spans.
    """

    module: libcst.Module
    """
    The tree, which keeps every comment and all whitespace of the source.
    """

    @cached_property
    def metadata(self) -> MetadataWrapper:
        """
        Resolves the metadata of the nodes of :attr:`module` itself, not of a copy.
        """
        return MetadataWrapper(self.module, unsafe_skip_copy=True)

    @cached_property
    def positions(self) -> Mapping[libcst.CSTNode, CodeRange]:
        """
        The code range of each node of :attr:`module`, keyed by the node itself; lines
        count from one, columns from zero.
        """
        return self.metadata.resolve(PositionProvider)
