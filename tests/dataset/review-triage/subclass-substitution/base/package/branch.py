"""
A branch of a remote.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Branch:
    """
    A branch, named on its remote.
    """

    name: str
    """
    The branch's name.
    """

    remote: str = "origin"
    """
    The remote holding it.
    """

    def reference(self) -> str:
        """
        :return: The branch's remote-tracking reference.
        """
        return f"{self.remote}/{self.name}"

    @property
    def description(self) -> str:
        """:return: The branch as a reader names it."""
        return f"{self.name} on {self.remote}"
