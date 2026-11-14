"""
The base of every specification: what one place in a module must become.
"""

from __future__ import annotations

from dataclasses import dataclass

import libcst
from libcst.metadata import CodeRange


@dataclass(frozen=True)
class Specification:
    """
    One place in a module that has to change, as an analysis found it; a subclass adds
    the facts the change depends on.
    """

    location: CodeRange
    """
    The code range of :attr:`node` in the module it was found in.
    """

    node: libcst.CSTNode
    """
    The node that has to change.
    """

    def overlaps(self, other: Specification) -> bool:
        """
        :return: Whether this place and *other* share any character, so that changing
            one changes the other.
        """
        return (other.location.start.line, other.location.start.column) < (
            self.location.end.line,
            self.location.end.column,
        ) and (self.location.start.line, self.location.start.column) < (
            other.location.end.line,
            other.location.end.column,
        )
