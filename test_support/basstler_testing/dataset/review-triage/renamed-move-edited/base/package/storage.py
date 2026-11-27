"""
The rows of a store and how they are read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from typing import Any

ROW_LIMIT: int = 1000
"""
The most rows a store holds.
"""


class _SessionKey(StrEnum):
    """
    The keys a session keeps its state under.
    """

    LOADED = "loaded"
    """
    Whether every row is loaded.
    """


@dataclass
class Reader:
    """
    Reads the rows of a store, once per session.
    """

    session: dict[str, Any]
    """
    The session's state.
    """

    def read(self, rows: list[Any]) -> list[Any]:
        """
        :param rows: The rows of a store.
        :return: The rows, unless the session already loaded them.
        """
        if self.session.get(_SessionKey.LOADED, False):
            return []
        self.session[_SessionKey.LOADED] = True
        return rows[:ROW_LIMIT]


@dataclass
class Store:
    """
    Holds rows.
    """

    rows: list[Any] = field(default_factory=list)
    """
    The rows held.
    """
