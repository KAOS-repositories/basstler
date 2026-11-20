"""
A branch that names itself for a reader.
"""

from __future__ import annotations

from dataclasses import dataclass

from package.branch import Branch


@dataclass(frozen=True)
class NamedBranch(Branch):
    """
    A :class:`Branch` that names itself for a reader.
    """

    @property
    def description(self) -> str:
        """:return: The branch as a reader names it."""
        return f"{self.name} on {self.remote}"
